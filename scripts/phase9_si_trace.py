"""Validate bounded oracle raw-SI DMA transactions without inferring parity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HEADER = ("sequence", "entry_frame", "entry_update", "entry_poll",
          "entry_vi", "return_frame", "return_update", "return_poll",
          "return_vi", "direction", "address", "caller", "before", "after")
MAX_ROWS = 256


def read(path: Path, focus: tuple[int, int]) -> list[dict]:
    if (not isinstance(focus, tuple) or len(focus) != 2 or
            any(type(value) is not int for value in focus) or
            focus[0] < 1 or focus[1] < focus[0] or
            focus[1] - focus[0] > 15):
        raise ValueError("SI transaction trace needs bounded updates")
    rows = []
    with Path(path).open(encoding="utf-8") as stream:
        if tuple(next(stream, "").rstrip("\n").split("\t")) != HEADER:
            raise ValueError("SI transaction trace header changed")
        for line in stream:
            fields = line.rstrip("\n").split("\t")
            if len(fields) != len(HEADER) or len(rows) >= MAX_ROWS:
                raise ValueError("SI transaction row is invalid or unbounded")
            row = dict(zip(HEADER, fields))
            for key in HEADER[:10]:
                if not row[key].isdigit():
                    raise ValueError("SI transaction clock is noncanonical")
                row[key] = int(row[key])
            for key in ("address", "caller"):
                value = row[key]
                if (len(value) != 10 or not value.startswith("0x") or
                        any(char not in "0123456789abcdef" for char in
                            value[2:])):
                    raise ValueError("SI transaction address is noncanonical")
                row[key] = int(value, 16)
            if (row["sequence"] != len(rows) + 1 or
                    not max(0, focus[0] - 2) <= row["entry_update"] <= focus[1] or
                    row["direction"] not in (0, 1) or
                    not 0x80000000 <= row["address"] <= 0x803FFFC0 or
                    not 0x80000000 <= row["caller"] <= 0x803FFFFC or
                    row["caller"] % 4 or
                    any(row["return_" + key] < row["entry_" + key]
                        for key in ("frame", "update", "poll", "vi")) or
                    (rows and any(row["entry_" + key] <
                                  rows[-1]["entry_" + key]
                                  for key in ("frame", "update", "poll", "vi")))):
                raise ValueError("SI transaction address or ordering changed")
            for key in ("before", "after"):
                value = row[key]
                if (len(value) != 128 or
                        any(char not in "0123456789abcdef" for char in value)):
                    raise ValueError("SI PIF payload is not 64 bytes of hex")
            rows.append(row)
    if not rows:
        raise ValueError("SI transaction trace is empty")
    return rows


def analyze(path: Path, focus: tuple[int, int]) -> dict:
    rows = read(path, focus)
    by_poll = {}
    for row in rows:
        item = by_poll.setdefault(row["entry_poll"],
                                  {"poll": row["entry_poll"], "writes": 0,
                                   "reads": 0, "changed_buffers": 0})
        item["writes" if row["direction"] == 1 else "reads"] += 1
        item["changed_buffers"] += row["before"] != row["after"]
    return {
        "kind": "jfg-phase9-oracle-si-transactions", "schema": 1,
        "trace_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "focused_updates": list(focus), "rows": len(rows),
        "write_calls": sum(row["direction"] == 1 for row in rows),
        "read_calls": sum(row["direction"] == 0 for row in rows),
        "changed_buffers": sum(row["before"] != row["after"] for row in rows),
        "callers": [f"0x{value:08x}" for value in
                    sorted({row["caller"] for row in rows})],
        "polls": [by_poll[key] for key in sorted(by_poll)],
        "alignment_validated": False, "parity_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--focus", nargs=2, type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.trace, tuple(args.focus)), indent=2,
                     sort_keys=True))


if __name__ == "__main__":
    main()
