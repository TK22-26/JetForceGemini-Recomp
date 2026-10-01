"""Compare raw CP1 or GPR words at one paired generated-function entry.

This diagnoses one already paired call. It does not establish route alignment
or full native/oracle parity.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re

from scripts.compare_phase9_entry_args import _rows as argument_rows


FPR_FIELDS = tuple(field for index in range(32)
                   for field in (f"f{index}_lo", f"f{index}_hi"))
GPR_FIELDS = tuple(field for index in range(32)
                   for field in (f"r{index}_lo", f"r{index}_hi"))
WORD = re.compile(r"0x[0-9a-fA-F]{8}\Z")


def register_rows(path: Path, selector: str, update: int, *, oracle: bool,
                  register_kind: str = "fpu") -> list[dict]:
    if register_kind not in ("fpu", "gpr"):
        raise ValueError("unsupported register kind")
    fields = FPR_FIELDS if register_kind == "fpu" else GPR_FIELDS
    lines = path.read_text(encoding="utf-8").splitlines()
    if oracle:
        if len(lines) < 3 or lines[-1] != f"result\ttrue\t{len(lines) - 2}":
            raise ValueError("oracle register trace is incomplete")
        lines = lines[:-1]
    if len(lines) < 2 or len(lines) > 1025:
        raise ValueError("register trace is empty or unbounded")
    expected = (("frame", "completed_updates", "controller_polls", "consumed_vi",
                 "pc", *fields) if oracle else
                ("update_candidate", "vi_retraces", "controller_polls",
                 "target", *fields))
    reader = csv.DictReader(lines, delimiter="\t")
    if tuple(reader.fieldnames or ()) != expected:
        raise ValueError("register trace header mismatch")
    rows = list(reader)
    if any(row is None or None in row or any(value is None for value in row.values())
           for row in rows):
        raise ValueError("register trace row is incomplete")
    selected = [row for row in rows if int(row[selector]) == update]
    if not selected:
        raise ValueError("register trace has no selected update calls")
    for row in selected:
        if any(not WORD.fullmatch(row[field]) for field in fields):
            raise ValueError("register trace has a non-32-bit word")
    return selected


def compare(native_dir: Path, oracle_dir: Path, *, native_update: int,
            oracle_completed: int, a0: int, a3: int | None = None,
            register_kind: str = "fpu") -> dict:
    if register_kind not in ("fpu", "gpr"):
        raise ValueError("unsupported register kind")
    fields = FPR_FIELDS if register_kind == "fpu" else GPR_FIELDS
    completion_key = f"entry_{register_kind}_trace_complete"
    trace_name = f"entry-{register_kind}.tsv"
    if (type(native_update) is not int or native_update < 1 or
            type(oracle_completed) is not int or oracle_completed < 0 or
            type(a0) is not int or not 0 <= a0 <= 0xFFFFFFFF or
            (a3 is not None and
             (type(a3) is not int or not 0 <= a3 <= 0xFFFFFFFF))):
        raise ValueError("invalid paired entry selector")
    native = json.loads((native_dir / "native-result.json").read_text(encoding="utf-8"))
    oracle = json.loads((oracle_dir / "oracle-result.json").read_text(encoding="utf-8"))
    if (native.get(completion_key) is not True or
            oracle.get(completion_key) is not True or
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
        raise ValueError("register trace provenance or completion mismatch")
    n_args = argument_rows(native_dir / "entry-args.tsv", "update_candidate",
                           native_update, oracle=False)
    o_args = argument_rows(oracle_dir / "entry-args.tsv", "completed_updates",
                           oracle_completed, oracle=True)
    n_registers = register_rows(native_dir / trace_name, "update_candidate",
                                native_update, oracle=False,
                                register_kind=register_kind)
    o_registers = register_rows(oracle_dir / trace_name, "completed_updates",
                                oracle_completed, oracle=True,
                                register_kind=register_kind)
    if len(n_args) != len(n_registers) or len(o_args) != len(o_registers):
        raise ValueError("register and argument call counts differ")
    selected_a0 = f"0x{a0:08x}"
    selected_a3 = f"0x{a3:08x}" if a3 is not None else None

    def select(arguments: list[dict], registers: list[dict], target_key: str) -> dict:
        positions = [index for index, row in enumerate(arguments)
                     if row["a0"] == selected_a0 and
                     (selected_a3 is None or row["a3"] == selected_a3)]
        if len(positions) != 1:
            raise ValueError("selected A0/A3 does not identify exactly one call")
        index = positions[0]
        metadata = (("frame", "completed_updates", "controller_polls",
                     "consumed_vi", "pc") if target_key == "pc" else
                    ("update_candidate", "vi_retraces", "controller_polls",
                     "target"))
        if (any(arguments[index][field] != registers[index][field]
                for field in metadata) or
                arguments[index][target_key] != native["entry_target"]):
            raise ValueError("register and argument call metadata differ")
        return registers[index]

    nrow = select(n_args, n_registers, "target")
    orow = select(o_args, o_registers, "pc")
    mismatches = [{"register_word": field, "native": nrow[field].lower(),
                   "oracle": orow[field].lower()} for field in fields
                  if nrow[field].lower() != orow[field].lower()]
    return {"kind": f"jfg-phase9-entry-{register_kind}-comparison", "schema": 1,
            "source_export": native["source_export"],
            "input_sha256": native["input_sha256"],
            "rom_sha256": native["rom_sha256"],
            "initial_flash_sha256": native["initial_flash_sha256"],
            "native_executable_sha256": native["executable_sha256"],
            "oracle_emulator_sha256": oracle["emulator_sha256"],
            "oracle_script_sha256": oracle["script_sha256"],
            "entry_pc": native["entry_target"], "a0": selected_a0,
            "a3": selected_a3,
            "native_update_candidate": native_update,
            "oracle_completed_updates": oracle_completed,
            "mismatch_count": len(mismatches), "mismatches": mismatches,
            "alignment_validated": False, "parity_verified": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_dir", type=Path)
    parser.add_argument("oracle_dir", type=Path)
    parser.add_argument("--native-update", type=int, required=True)
    parser.add_argument("--oracle-completed", type=int, required=True)
    parser.add_argument("--a0", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--a3", type=lambda value: int(value, 0),
                        help="disambiguate repeated A0 calls")
    parser.add_argument("--register-kind", choices=("fpu", "gpr"), default="fpu")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare(args.native_dir, args.oracle_dir,
                     native_update=args.native_update,
                     oracle_completed=args.oracle_completed, a0=args.a0,
                     a3=args.a3, register_kind=args.register_kind)
    rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
