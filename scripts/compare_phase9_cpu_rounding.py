#!/usr/bin/env python3
"""Adjudicate the isolated CVT.W.S microtest without treating an emulator as hardware."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.phase95_bridge import digest


MANUAL_URL = (
    "https://www.bitsavers.org/components/nec/mips/"
    "1995_NEC_VR4300_MIPS_RISC_Microprocessor_Users_Manual.pdf"
)


def checked_result(path: Path, core: str) -> dict:
    path = path.resolve(strict=True)
    result = json.loads(path.read_text(encoding="utf-8"))
    observed = result.get("observed")
    trace = path.parent / "cpu-rounding.tsv"
    if (result.get("kind") != "jfg-phase9-cpu-rounding-microtest" or
            result.get("acceptance") is not False or
            result.get("complete") is not True or
            result.get("exit_code") != 0 or
            result.get("core") != core or
            not isinstance(observed, dict) or
            result.get("trace_sha256") != digest(trace) or
            observed.get("operand_bits") != "0x440ba000" or
            observed.get("rounding_mode") != 0 or
            type(observed.get("converted_integer")) is not int or
            not 0 <= observed["converted_integer"] <= 0xFFFFFFFF):
        raise ValueError(f"incomplete or inconsistent {core} CPU microtest")
    return result


def compare(mupen: Path, ares: Path) -> dict:
    first = checked_result(mupen, "Mupen64Plus")
    second = checked_result(ares, "Ares64")
    for key in ("rom_sha256", "emulator_sha256", "runtime_sha256",
                "script_sha256"):
        if not first.get(key) or first[key] != second.get(key):
            raise ValueError(f"CPU microtests do not share pinned {key}")
    if first.get("config_sha256") == second.get("config_sha256"):
        raise ValueError("CPU microtests did not select distinct core configs")
    values = {"Mupen64Plus": first["observed"]["converted_integer"],
              "Ares64": second["observed"]["converted_integer"]}
    return {"kind": "jfg-phase9-cpu-rounding-adjudication", "schema": 1,
            "acceptance": False, "parity_verified": False,
            "rom_sha256": first["rom_sha256"],
            "source_results": {"Mupen64Plus": digest(mupen),
                               "Ares64": digest(ares)},
            "operand_bits": "0x440ba000", "operand_decimal": 558.5,
            "rounding_mode": 0,
            "vr4300_manual_rule": "nearest; exact ties to even",
            "vr4300_manual_url": MANUAL_URL,
            "manual_expected_integer": 558,
            "observed_integers": values,
            "cores_disagree": values["Mupen64Plus"] != values["Ares64"],
            "ares_agrees_with_manual": values["Ares64"] == 558,
            "mupen_agrees_with_manual": values["Mupen64Plus"] == 558,
            "disposition": (
                "mupen_oracle_semantics_conflict"
                if values == {"Mupen64Plus": 559, "Ares64": 558}
                else "inconclusive"
            ),
            "caveat": "isolated CPU instruction only; not game-route alignment or parity"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mupen", type=Path)
    parser.add_argument("ares", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    report = compare(args.mupen, args.ares)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"disposition": report["disposition"],
                      "observed_integers": report["observed_integers"],
                      "output": str(args.output)}))


if __name__ == "__main__":
    main()
