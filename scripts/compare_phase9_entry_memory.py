"""Compare bounded A1-A3 input memory at one paired generated-function call.

The selected A0/A3 tuple must identify exactly one call on each side. This
reports local input differences, not global route alignment or parity.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re

from scripts.compare_phase9_entry_args import _rows as argument_rows


MEMORY_SPANS = (128, 256)


def memory_rows(path: Path, selector: str, update: int, *, oracle: bool):
    lines = path.read_text(encoding="utf-8").splitlines()
    if oracle:
        if len(lines) < 3 or lines[-1] != f"result\ttrue\t{len(lines) - 2}":
            raise ValueError("oracle entry memory trace is incomplete")
        lines = lines[:-1]
    if len(lines) < 2 or len(lines) > 1025:
        raise ValueError("entry memory trace is empty or unbounded")
    reader = csv.DictReader(lines, delimiter="\t")
    prefix = (("frame", "completed_updates", "controller_polls", "consumed_vi",
               "pc") if oracle else
              ("update_candidate", "vi_retraces", "controller_polls", "target"))
    span = next((size for size in MEMORY_SPANS
                 if tuple(reader.fieldnames or ()) ==
                 (*prefix, *(f"a{index}_{size}" for index in range(1, 4)))), None)
    if span is None:
        raise ValueError("entry memory trace header mismatch")
    rows = list(reader)
    if any(row is None or None in row or any(value is None for value in row.values())
           for row in rows):
        raise ValueError("entry memory trace row is incomplete")
    selected = [row for row in rows if int(row[selector]) == update]
    if not selected:
        raise ValueError("entry memory trace has no selected update calls")
    fields = tuple(f"a{index}_{span}" for index in range(1, 4))
    value_pattern = re.compile(rf"[0-9a-fA-F]{{{span * 2}}}\Z")
    if any(not value_pattern.fullmatch(row[field]) for row in selected
           for field in fields):
        raise ValueError("entry memory trace has invalid bounded data")
    return selected, span


def compare(native_dir: Path, oracle_dir: Path, *, native_update: int,
            oracle_completed: int, a0: int, a3: int) -> dict:
    if (type(native_update) is not int or native_update < 1 or
            type(oracle_completed) is not int or oracle_completed < 0 or
            type(a0) is not int or not 0 <= a0 <= 0xFFFFFFFF or
            type(a3) is not int or not 0 <= a3 <= 0xFFFFFFFF):
        raise ValueError("invalid paired entry selector")
    native = json.loads((native_dir / "native-result.json").read_text(encoding="utf-8"))
    oracle = json.loads((oracle_dir / "oracle-result.json").read_text(encoding="utf-8"))
    if (native.get("entry_memory_trace_complete") is not True or
            oracle.get("entry_memory_trace_complete") is not True or
            native.get("entry_trace_complete") is not True or
            oracle.get("entry_trace_complete") is not True or
            native.get("source_export") != oracle.get("source_export") or
            native.get("input_sha256") != oracle.get("input_sha256") or
            native.get("rom_sha256") != oracle.get("rom_sha256") or
            oracle.get("initial_flash_matches_candidate") is not True or
            native.get("initial_flash_sha256") !=
            oracle.get("oracle_initial_flash_sha256") or
            not native.get("entry_target") or not oracle.get("entry_pc") or
            native["entry_target"] != oracle["entry_pc"]):
        raise ValueError("entry memory provenance or completion mismatch")
    n_args = argument_rows(native_dir / "entry-args.tsv", "update_candidate",
                           native_update, oracle=False)
    o_args = argument_rows(oracle_dir / "entry-args.tsv", "completed_updates",
                           oracle_completed, oracle=True)
    n_mem, n_span = memory_rows(native_dir / "entry-memory.tsv", "update_candidate",
                                native_update, oracle=False)
    o_mem, o_span = memory_rows(oracle_dir / "entry-memory.tsv", "completed_updates",
                                oracle_completed, oracle=True)
    if n_span != o_span or len(n_args) != len(n_mem) or len(o_args) != len(o_mem):
        raise ValueError("memory and argument call counts differ")
    selected_a0, selected_a3 = f"0x{a0:08x}", f"0x{a3:08x}"

    def select(arguments: list[dict], memories: list[dict], *, oracle_side: bool):
        positions = [index for index, row in enumerate(arguments)
                     if row["a0"] == selected_a0 and row["a3"] == selected_a3]
        if len(positions) != 1:
            raise ValueError("A0/A3 does not identify exactly one call")
        index = positions[0]
        metadata = (("frame", "completed_updates", "controller_polls",
                     "consumed_vi", "pc") if oracle_side else
                    ("update_candidate", "vi_retraces", "controller_polls",
                     "target"))
        if any(arguments[index][field] != memories[index][field]
               for field in metadata):
            raise ValueError("memory and argument call metadata differ")
        return arguments[index], memories[index]

    narg, nrow = select(n_args, n_mem, oracle_side=False)
    oarg, orow = select(o_args, o_mem, oracle_side=True)
    if any(narg[field] != oarg[field] for field in ("a0", "a1", "a2", "a3")):
        raise ValueError("entry pointer arguments differ")
    mismatches = []
    for field in (f"a{index}_{n_span}" for index in range(1, 4)):
        for offset in range(0, n_span, 4):
            start = offset * 2
            nvalue = nrow[field][start:start + 8].lower()
            ovalue = orow[field][start:start + 8].lower()
            if nvalue != ovalue:
                mismatches.append({"argument": field[:2], "offset": offset,
                                   "native": "0x" + nvalue,
                                   "oracle": "0x" + ovalue})
    return {"kind": "jfg-phase9-entry-memory-comparison", "schema": 1,
            "source_export": native["source_export"],
            "input_sha256": native["input_sha256"],
            "rom_sha256": native["rom_sha256"],
            "initial_flash_sha256": native["initial_flash_sha256"],
            "native_executable_sha256": native["executable_sha256"],
            "oracle_emulator_sha256": oracle["emulator_sha256"],
            "oracle_script_sha256": oracle["script_sha256"],
            "entry_pc": native["entry_target"], "a0": selected_a0,
            "a1": narg["a1"], "a2": narg["a2"], "a3": selected_a3,
            "native_update_candidate": native_update,
            "oracle_completed_updates": oracle_completed,
            "memory_span_bytes": n_span,
            "mismatch_count": len(mismatches), "mismatches": mismatches,
            "alignment_validated": False, "parity_verified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_dir", type=Path)
    parser.add_argument("oracle_dir", type=Path)
    parser.add_argument("--native-update", type=int, required=True)
    parser.add_argument("--oracle-completed", type=int, required=True)
    parser.add_argument("--a0", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--a3", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare(args.native_dir, args.oracle_dir,
                     native_update=args.native_update,
                     oracle_completed=args.oracle_completed,
                     a0=args.a0, a3=args.a3)
    rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
