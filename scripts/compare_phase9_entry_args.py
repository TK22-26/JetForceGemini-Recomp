"""Compare bounded native/oracle function-entry arguments at a focused update.

These are guest-level inputs to one selected function, not proof of global
runtime alignment or code parity. The caller must supply a previously paired
native update candidate and oracle completed-update index.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FIELDS = ("a0", "a1", "a2", "a3")


def _rows(path: Path, selector: str, update: int, *, oracle: bool) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if oracle:
        if len(lines) < 3 or lines[-1].split("\t") != ["result", "true", str(len(lines) - 2)]:
            raise ValueError("oracle entry trace is incomplete")
        lines = lines[:-1]
    if len(lines) < 2 or len(lines) > 1025:
        raise ValueError("entry trace is empty or unbounded")
    reader = csv.DictReader(lines, delimiter="\t")
    expected = (("frame", "completed_updates", "controller_polls", "consumed_vi",
                 "pc", *FIELDS) if oracle else
                ("update_candidate", "vi_retraces", "controller_polls",
                 "target", *FIELDS))
    if tuple(reader.fieldnames or ()) != expected:
        raise ValueError("entry trace header mismatch")
    records = list(reader)
    if any(row is None or any(value is None for value in row.values())
           for row in records):
        raise ValueError("entry trace row is incomplete")
    selected = [row for row in records if int(row[selector]) == update]
    if not selected:
        raise ValueError("entry trace has no selected update calls")
    for row in selected:
        for field in FIELDS:
            value = row[field]
            if not value.startswith("0x") or not 3 <= len(value) <= 10:
                raise ValueError("entry trace argument is not a 32-bit word")
            try:
                row[field] = f"0x{int(value[2:], 16):08x}"
            except ValueError as error:
                raise ValueError("entry trace argument is not hexadecimal") from error
    return selected


def compare(native_dir: Path, oracle_dir: Path, *, native_update: int,
            oracle_completed: int) -> dict:
    if (type(native_update) is not int or native_update < 1 or
            type(oracle_completed) is not int or oracle_completed < 0):
        raise ValueError("invalid focused entry update pair")
    native = json.loads((native_dir / "native-result.json").read_text(encoding="utf-8"))
    oracle = json.loads((oracle_dir / "oracle-result.json").read_text(encoding="utf-8"))
    if (native.get("entry_trace_complete") is not True or
            oracle.get("entry_trace_complete") is not True or
            native.get("input_sha256") != oracle.get("input_sha256") or
            native.get("rom_sha256") != oracle.get("rom_sha256") or
            native.get("source_export") != oracle.get("source_export") or
            oracle.get("initial_flash_matches_candidate") is not True or
            not native.get("initial_flash_sha256") or
            native.get("initial_flash_sha256") != oracle.get("oracle_initial_flash_sha256") or
            not native.get("entry_target") or not oracle.get("entry_pc")):
        raise ValueError("entry trace provenance or completion mismatch")
    nrows = _rows(native_dir / "entry-args.tsv", "update_candidate",
                  native_update, oracle=False)
    orows = _rows(oracle_dir / "entry-args.tsv", "completed_updates",
                  oracle_completed, oracle=True)
    if (any(int(row["target"], 16) != int(native["entry_target"], 16)
            for row in nrows) or
            any(int(row["pc"], 16) != int(oracle["entry_pc"], 16)
                for row in orows)):
        raise ValueError("entry trace target does not match pinned probe")
    calls = []
    for index in range(max(len(nrows), len(orows))):
        nrow = nrows[index] if index < len(nrows) else None
        orow = orows[index] if index < len(orows) else None
        arguments = {}
        for field in FIELDS:
            nvalue = nrow[field] if nrow else None
            ovalue = orow[field] if orow else None
            arguments[field] = {"native": nvalue, "oracle": ovalue,
                                "match": nvalue == ovalue if nrow and orow else False}
        calls.append({"index": index, "arguments": arguments,
                      "native_vi_retraces": int(nrow["vi_retraces"]) if nrow else None,
                      "oracle_consumed_vi": int(orow["consumed_vi"]) if orow else None})
    mismatches = [row["index"] for row in calls if any(
        not item["match"] for item in row["arguments"].values())]
    return {
        "kind": "jfg-phase9-entry-argument-comparison", "schema": 1,
        "source_export": native["source_export"],
        "input_sha256": native["input_sha256"],
        "rom_sha256": native["rom_sha256"],
        "initial_flash_sha256": native["initial_flash_sha256"],
        "native_executable_sha256": native["executable_sha256"],
        "oracle_emulator_sha256": oracle["emulator_sha256"],
        "oracle_config_sha256": oracle["config_sha256"],
        "oracle_runtime_sha256": oracle["runtime_sha256"],
        "oracle_script_sha256": oracle["script_sha256"],
        "native_entry_target": native["entry_target"],
        "oracle_entry_pc": oracle["entry_pc"],
        "native_update_candidate": native_update,
        "oracle_completed_updates": oracle_completed,
        "native_call_count": len(nrows), "oracle_call_count": len(orows),
        "first_argument_mismatch_call": mismatches[0] if mismatches else None,
        "all_a0_match": len(nrows) == len(orows) and all(
            row["arguments"]["a0"]["match"] for row in calls),
        "calls": calls,
        "alignment_validated": False, "parity_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_dir", type=Path)
    parser.add_argument("oracle_dir", type=Path)
    parser.add_argument("--native-update", type=int, required=True)
    parser.add_argument("--oracle-completed", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare(args.native_dir, args.oracle_dir,
                     native_update=args.native_update,
                     oracle_completed=args.oracle_completed)
    rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
