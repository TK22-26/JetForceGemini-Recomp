"""Compare one guest word at each completed game-update boundary.

The first word mismatch is a diagnostic frontier, not proof of aligned input,
Controller Pak state, or an incorrect generated guest function.
"""

from __future__ import annotations

import argparse
import hashlib
from itertools import zip_longest
import json
from pathlib import Path


HEADER = ("update", "controller_polls", "vi", "frame", "address", "value")


def validate_update_word(address: int | None, update_hashes: bool) -> int | None:
    if address is None:
        return None
    if (type(address) is not int or not update_hashes or
            not 0x80000000 <= address <= 0x803FFFFC or address % 4):
        raise ValueError("update word requires a hashed KSEG0 guest word")
    return address


def read(path: Path, address: int) -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8") as stream:
        if tuple(next(stream, "").rstrip("\n").split("\t")) != HEADER:
            raise ValueError("update-word trace header changed")
        previous = None
        for line in stream:
            fields = line.rstrip("\n").split("\t")
            if len(fields) != len(HEADER) or len(rows) >= 1_000_000:
                raise ValueError("update-word trace row is invalid or unbounded")
            row = dict(zip(HEADER, fields))
            try:
                for key in HEADER[:4]:
                    row[key] = int(row[key])
                for key in HEADER[4:]:
                    if (len(row[key]) != 10 or not row[key].startswith("0x") or
                            row[key][2:].lower() != row[key][2:]):
                        raise ValueError("noncanonical hexadecimal word")
                    row[key] = int(row[key], 16)
            except ValueError as error:
                raise ValueError("update-word trace value is invalid") from error
            if (row["update"] != len(rows) + 1 or row["address"] != address or
                    row["controller_polls"] < 0 or row["vi"] < 0 or
                    row["frame"] < 0 or
                    (previous is not None and any(row[key] < previous[key]
                        for key in ("controller_polls", "vi", "frame")))):
                raise ValueError("update-word trace order or clock changed")
            rows.append(row)
            previous = row
    if not rows:
        raise ValueError("update-word trace is empty")
    return rows


def _sha256(path: Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def compare(native: Path, oracle: Path, address: int) -> dict:
    address = validate_update_word(address, True)
    left, right = read(native, address), read(oracle, address)
    first = None
    matching = 0
    for index, (a, b) in enumerate(zip_longest(left, right), 1):
        if a is None or b is None:
            first = {"update": index, "reason": "missing-update",
                     "missing": "native" if a is None else "oracle"}
            break
        if a["value"] != b["value"]:
            first = {
                "update": index, "reason": "word-difference",
                "native_value": f"0x{a['value']:08x}",
                "oracle_value": f"0x{b['value']:08x}",
                "native_clock": {key: a[key] for key in HEADER[1:4]},
                "oracle_clock": {key: b[key] for key in HEADER[1:4]},
            }
            break
        matching = index
    return {
        "kind": "jfg-phase9-update-word-comparison", "schema": 1,
        "address": f"0x{address:08x}",
        "native_sha256": _sha256(native), "oracle_sha256": _sha256(oracle),
        "native_updates": len(left), "oracle_updates": len(right),
        "matching_update_prefix": matching,
        "first_difference": first,
        "alignment_validated": False, "parity_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("--address", type=lambda value: int(value, 0),
                        required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.native, args.oracle, args.address),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
