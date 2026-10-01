"""Validate and compare bounded bytes returned by osContGetReadData.

Same-poll returned bytes are diagnostic only; they do not prove identical
within-call SI timing, initial Pak state, or full route alignment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.phase9_event_trace import validate_windows


HEADER = ("sequence", "poll", "completed_updates", "vi", "frame",
          "address", "data")
MAX_ROWS = 256


def read(path: Path, windows: tuple[tuple[int, int], ...]) -> list[dict]:
    windows = validate_windows(windows, poll_hashes=True,
                               update_hashes=True, vi_trace=True)
    if not windows:
        raise ValueError("controller-return trace needs bounded poll windows")
    rows = []
    with Path(path).open(encoding="utf-8") as stream:
        if tuple(next(stream, "").rstrip("\n").split("\t")) != HEADER:
            raise ValueError("controller-return trace header changed")
        for line in stream:
            fields = line.rstrip("\n").split("\t")
            if len(fields) != len(HEADER) or len(rows) >= MAX_ROWS:
                raise ValueError("controller-return trace row is invalid or unbounded")
            row = dict(zip(HEADER, fields))
            try:
                for key in HEADER[:5]:
                    row[key] = int(row[key])
                raw_address = row["address"]
                if (len(raw_address) != 10 or not raw_address.startswith("0x") or
                        raw_address[2:].lower() != raw_address[2:]):
                    raise ValueError("noncanonical address")
                row["address"] = int(raw_address, 16)
            except ValueError as error:
                raise ValueError("controller-return trace value is invalid") from error
            data = row["data"]
            if (len(data) != 48 or data.lower() != data or
                    any(char not in "0123456789abcdef" for char in data) or
                    row["sequence"] != len(rows) + 1 or
                    not any(first <= row["poll"] <= last
                            for first, last in windows) or
                    not 0x80000000 <= row["address"] <= 0x803FFFE8 or
                    any(row[key] < 0 for key in HEADER[1:5]) or
                    (rows and any(row[key] < rows[-1][key]
                                  for key in HEADER[1:5]))):
                raise ValueError("controller-return data or clocks changed")
            rows.append(row)
    if not rows:
        raise ValueError("controller-return trace is empty")
    return rows


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def compare(native: Path, oracle: Path,
            windows: tuple[tuple[int, int], ...]) -> dict:
    left, right = read(native, windows), read(oracle, windows)
    by_poll = []
    for rows in (left, right):
        selected = {}
        for row in rows:
            selected.setdefault(row["poll"], []).append(row)
        by_poll.append(selected)
    common = sorted(set(by_poll[0]) & set(by_poll[1]))
    if not common:
        raise ValueError("controller-return traces have no shared poll")
    first = None
    matching = 0
    for poll in common:
        a, b = by_poll[0][poll], by_poll[1][poll]
        a_values = [(row["address"], row["data"]) for row in a]
        b_values = [(row["address"], row["data"]) for row in b]
        if a_values != b_values:
            first = {"poll": poll, "native": a_values,
                     "oracle": b_values}
            break
        matching += 1
    return {
        "kind": "jfg-phase9-controller-return-comparison", "schema": 1,
        "windows": [list(window) for window in windows],
        "native_sha256": _digest(native), "oracle_sha256": _digest(oracle),
        "native_rows": len(left), "oracle_rows": len(right),
        "shared_polls": len(common), "matching_shared_poll_prefix": matching,
        "first_same_poll_difference": first,
        "native_only_polls": sorted(set(by_poll[0]) - set(by_poll[1])),
        "oracle_only_polls": sorted(set(by_poll[1]) - set(by_poll[0])),
        "alignment_validated": False, "parity_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("--window", action="append", required=True)
    args = parser.parse_args()
    windows = tuple(tuple(int(item) for item in text.split(":"))
                    for text in args.window)
    print(json.dumps(compare(args.native, args.oracle, windows),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
