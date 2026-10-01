#!/usr/bin/env python3
"""Compare explicitly paired native/oracle decode-PC calls; never infer timing alignment."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from scripts.phase95_native_replay import (
    INSTRUCTION_PROBE_HEADER, INSTRUCTION_PROBE_PCS,
)


FIELDS = ("r4", "r5", "r6", "r7", "r10", "r15", "r19", "r20",
          "r21", "r23", "r25", "f4_lo", "f22_lo", "f23_odd_lo")


def rows(path: Path, required: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames is None or any(name not in reader.fieldnames
                                           for name in required):
            raise ValueError(f"missing probe columns: {path}")
        result = list(reader)
    if result and result[-1].get(reader.fieldnames[0]) == "result":
        trailer = result.pop()
        if (trailer.get(reader.fieldnames[1]) != "true" or
                trailer.get(reader.fieldnames[2]) != str(len(result))):
            raise ValueError(f"invalid probe trailer: {path}")
    if not result or any(None in row or None in row.values() for row in result):
        raise ValueError(f"empty or malformed probe: {path}")
    return result


def select(candidates: list[dict[str, str]], *, update_field: str,
           update: int, pc: int, a0_field: str, a0: int,
           occurrence: int) -> tuple[int, dict[str, str]]:
    matches = [(index, row) for index, row in enumerate(candidates)
               if int(row[update_field]) == update and
               int(row["pc"], 16) == pc and
               int(row[a0_field], 16) == a0]
    if occurrence < 1 or occurrence > len(matches):
        raise ValueError(f"expected occurrence {occurrence}, found {len(matches)} "
                         f"at 0x{pc:08x} update {update}")
    return matches[occurrence - 1]


def compare(native: Path, oracles: dict[int, Path], *, native_update: int,
            oracle_completed_update: int, a0: int, occurrence: int) -> dict:
    native_result = json.loads((native / "native-result.json").read_text())
    if not native_result.get("instruction_probe_trace_complete") or \
            native_result.get("acceptance") is not False:
        raise ValueError("native diagnostic probe is not complete")
    native_rows = rows(native / "instruction-probe.tsv",
                       INSTRUCTION_PROBE_HEADER)
    comparisons = []
    input_sha = native_result.get("input_sha256")
    oracle_identity = None
    if set(oracles) != set(INSTRUCTION_PROBE_PCS):
        raise ValueError("one oracle run is required for each instrumented PC")
    for pc in INSTRUCTION_PROBE_PCS:
        oracle = oracles[pc]
        result = json.loads((oracle / "oracle-result.json").read_text())
        if (result.get("entry_pc") != f"0x{pc:08x}" or
                result.get("input_sha256") != input_sha or
                result.get("rom_sha256") != native_result.get("rom_sha256") or
                result.get("oracle_initial_flash_sha256") !=
                    native_result.get("initial_flash_sha256") or
                result.get("initial_flash_matches_candidate") is not True or
                not result.get("entry_gpr_trace_complete") or
                not result.get("entry_fpu_trace_complete") or
                result.get("acceptance") is not False):
            raise ValueError(f"oracle diagnostic probe is not comparable: {oracle}")
        identity = tuple(result.get(key) for key in
                         ("emulator_sha256", "runtime_sha256", "config_sha256"))
        if oracle_identity is None:
            oracle_identity = identity
        elif identity != oracle_identity:
            raise ValueError("oracle PC runs use different emulator identities")
        gprs = rows(oracle / "entry-gpr.tsv",
                    ("completed_updates", "pc", "r4_lo", *(
                        f"r{index}_lo" for index in (5, 6, 7, 10, 15, 19,
                                                    20, 21, 23, 25))))
        fprs = rows(oracle / "entry-fpu.tsv",
                    ("completed_updates", "pc", "f4_lo", "f22_lo", "f23_lo"))
        fcrs = rows(oracle / "entry-fcr.tsv", ("completed_updates", "pc", "fcr31")) \
            if result.get("entry_fcr_trace_complete") else None
        _, native_row = select(native_rows, update_field="update_candidate",
                               update=native_update, pc=pc, a0_field="r4",
                               a0=a0, occurrence=occurrence)
        oracle_index, oracle_row = select(
            gprs, update_field="completed_updates",
            update=oracle_completed_update, pc=pc,
            a0_field="r4_lo", a0=a0, occurrence=occurrence)
        if oracle_index >= len(fprs):
            raise ValueError(f"oracle FPU trace has fewer calls: {oracle}")
        fpr_row = fprs[oracle_index]
        if any(oracle_row[key] != fpr_row[key] for key in
               ("frame", "completed_updates", "controller_polls",
                "consumed_vi", "pc")):
            raise ValueError(f"oracle GPR/FPR call order differs: {oracle}")
        fcr_value = None
        if fcrs is not None:
            if oracle_index >= len(fcrs) or any(
                    oracle_row[key] != fcrs[oracle_index][key] for key in
                    ("frame", "completed_updates", "controller_polls",
                     "consumed_vi", "pc")):
                raise ValueError(f"oracle GPR/FCR call order differs: {oracle}")
            fcr_value = fcrs[oracle_index]["fcr31"]
        differences = {}
        for field in FIELDS:
            oracle_field = ("f23_lo" if field == "f23_odd_lo" else
                            f"{field}_lo" if field.startswith("r") else field)
            oracle_value = (fpr_row if field.startswith("f") else oracle_row)[
                oracle_field]
            if int(native_row[field], 16) != int(oracle_value, 16):
                differences[field] = {"native": native_row[field],
                                      "oracle": oracle_value}
        comparisons.append({"pc": f"0x{pc:08x}", "native": native_row,
                            "oracle_location": {key: oracle_row[key] for key in
                                                ("frame", "completed_updates",
                                                 "controller_polls", "consumed_vi")},
                            "oracle_fcr31": fcr_value,
                            "differences": differences})
    return {"kind": "jfg-phase9-instruction-probe-comparison", "schema": 1,
            "acceptance": False, "input_sha256": input_sha,
            "native_update_candidate": native_update,
            "oracle_completed_updates": oracle_completed_update,
            "a0": f"0x{a0:08x}", "occurrence": occurrence,
            "comparisons": comparisons,
            "all_equal": all(not item["differences"] for item in comparisons),
            "caveat": "explicit diagnostic pairing, not validated global input-clock alignment"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--oracle", action="append", required=True,
                        metavar="PC=DIR")
    parser.add_argument("--native-update", type=int, required=True)
    parser.add_argument("--oracle-completed-update", type=int, required=True)
    parser.add_argument("--a0", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--occurrence", type=int, default=1)
    args = parser.parse_args()
    oracles = {}
    for spec in args.oracle:
        pc_text, separator, path = spec.partition("=")
        if separator != "=" or not path:
            parser.error("--oracle must be PC=DIR")
        pc = int(pc_text, 0)
        if pc in oracles:
            parser.error("duplicate oracle PC")
        oracles[pc] = Path(path)
    report = compare(args.native, oracles,
                     native_update=args.native_update,
                     oracle_completed_update=args.oracle_completed_update,
                     a0=args.a0, occurrence=args.occurrence)
    if args.output.exists():
        parser.error("output already exists")
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "all_equal": report["all_equal"],
                      "differences": {item["pc"]: list(item["differences"])
                                      for item in report["comparisons"]}}))


if __name__ == "__main__":
    main()
