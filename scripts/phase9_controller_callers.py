"""Validate bounded BizHawk osContGetReadData caller observations."""

from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.phase9_event_trace import validate_windows


HEADER = ("sequence", "poll", "completed_updates", "frame", "vi",
          "caller", "destination")
MAX_ROWS = 256


def read(path: Path, windows) -> list[dict]:
    windows = validate_windows(windows, poll_hashes=True,
                               update_hashes=True, vi_trace=True)
    if not windows:
        raise ValueError("controller caller trace needs bounded windows")
    rows = []
    with Path(path).open(encoding="utf-8") as stream:
        if tuple(next(stream, "").rstrip("\n").split("\t")) != HEADER:
            raise ValueError("controller caller trace header changed")
        for line in stream:
            fields = line.rstrip("\n").split("\t")
            if len(fields) != len(HEADER) or len(rows) >= MAX_ROWS:
                raise ValueError("controller caller trace row is invalid or unbounded")
            row = dict(zip(HEADER, fields))
            try:
                for key in HEADER[:5]:
                    if not row[key].isdigit():
                        raise ValueError("noncanonical clock")
                    row[key] = int(row[key])
                for key in HEADER[5:]:
                    raw = row[key]
                    if (len(raw) != 10 or not raw.startswith("0x") or
                            any(c not in "0123456789abcdef" for c in raw[2:])):
                        raise ValueError("noncanonical address")
                    row[key] = int(raw, 16)
            except ValueError as error:
                raise ValueError("controller caller trace value is invalid") from error
            if (row["sequence"] != len(rows) + 1 or
                    not any(first <= row["poll"] <= last
                            for first, last in windows) or
                    not 0x80000000 <= row["caller"] <= 0x803FFFFC or
                    row["caller"] % 4 or
                    not 0x80000000 <= row["destination"] <= 0x803FFFE8 or
                    (rows and any(row[key] < rows[-1][key]
                                  for key in ("poll", "completed_updates",
                                              "frame", "vi")))):
                raise ValueError("controller caller address or clocks changed")
            rows.append(row)
    return rows


def analyze(path: Path, windows) -> dict:
    windows = validate_windows(windows, poll_hashes=True,
                               update_hashes=True, vi_trace=True)
    rows = read(path, windows)
    by_window = []
    for first, last in windows:
        selected = [row for row in rows if first <= row["poll"] <= last]
        callers = sorted({row["caller"] for row in selected})
        by_window.append({"window": [first, last], "rows": len(selected),
                          "callers": [f"0x{value:08x}" for value in callers],
                          "unique_caller": f"0x{callers[0]:08x}"
                          if len(callers) == 1 else None})
    return {
        "kind": "jfg-phase9-controller-caller-report", "schema": 1,
        "trace_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "rows": len(rows), "windows": by_window,
        "alignment_validated": False, "parity_verified": False,
    }
