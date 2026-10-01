"""Validate and compare bounded native/BizHawk event-order diagnostics.

Event order can explain poll-state lag. It is not evidence that the producers
have the same initial Pak state or that their VI clocks are aligned.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import argparse


HEADER = ("sequence", "event", "poll", "completed_updates", "frame", "vi",
          "start_calls", "get_calls", "connected", "buttons", "stick_x",
          "stick_y")
COMMON_EVENTS = frozenset(("start-entry", "get-entry", "input-poll",
                           "update-begin", "update-end", "vi-consumed"))
NATIVE_ONLY_EVENTS = frozenset(("start-exit", "get-exit"))


def validate_windows(windows, *, poll_hashes: bool, update_hashes: bool,
                     vi_trace: bool = True) -> tuple[tuple[int, int], ...]:
    if not windows:
        return ()
    if (not isinstance(windows, (tuple, list)) or len(windows) > 2 or
            not poll_hashes or not update_hashes or not vi_trace):
        raise ValueError("event windows require poll, update, and VI tracing")
    result = []
    previous_end = -1
    for window in windows:
        if (not isinstance(window, (tuple, list)) or len(window) != 2 or
                any(type(value) is not int for value in window)):
            raise ValueError("event window needs integer first/last polls")
        first, last = window
        if (first <= previous_end or first < 0 or last < first or
                last - first > 31 or last > 1_000_000):
            raise ValueError("event windows must be ordered, disjoint, and bounded")
        result.append((first, last))
        previous_end = last
    return tuple(result)


def spec(windows: tuple[tuple[int, int], ...]) -> str:
    return ",".join(f"{first}:{last}" for first, last in windows)


def read(path: Path, windows: tuple[tuple[int, int], ...],
         side: str) -> list[dict]:
    if side not in ("native", "oracle") or not windows:
        raise ValueError("event trace needs a side and bounded windows")
    with Path(path).open(encoding="utf-8") as stream:
        if tuple(next(stream, "").rstrip("\n").split("\t")) != HEADER:
            raise ValueError("event trace header mismatch")
        rows = []
        input_polls = Counter()
        previous = None
        previous_input_poll = -1
        for line in stream:
            fields = line.rstrip("\n").split("\t")
            if len(fields) != len(HEADER) or len(rows) >= 4096:
                raise ValueError("event trace row width/count is invalid")
            row = dict(zip(HEADER, fields))
            if row["event"] not in COMMON_EVENTS | (
                    NATIVE_ONLY_EVENTS if side == "native" else frozenset()):
                raise ValueError("event trace contains an unsupported event")
            try:
                for key in HEADER:
                    if key != "event":
                        row[key] = int(row[key])
            except ValueError as error:
                raise ValueError("event trace contains a noninteger field") from error
            if (row["sequence"] != len(rows) + 1 or
                    not any(first <= row["poll"] <= last
                            for first, last in windows) or
                    row["connected"] not in (0, 1) or
                    not 0 <= row["buttons"] <= 65535 or
                    not -128 <= row["stick_x"] <= 127 or
                    not -128 <= row["stick_y"] <= 127 or
                    any(row[key] < 0 for key in (
                        "completed_updates", "frame", "vi", "start_calls",
                        "get_calls"))):
                raise ValueError("event trace row is out of range")
            if previous is not None and any(row[key] < previous[key] for key in (
                    "completed_updates", "frame", "vi", "start_calls",
                    "get_calls")):
                raise ValueError("event trace clocks or call counts decreased")
            if row["event"] == "input-poll":
                if row["poll"] <= previous_input_poll:
                    raise ValueError("event trace input poll order changed")
                input_polls[row["poll"]] += 1
                previous_input_poll = row["poll"]
            rows.append(row)
            previous = row
    expected = {poll for first, last in windows for poll in range(first, last + 1)}
    if set(input_polls) != expected or any(count != 1 for count in input_polls.values()):
        raise ValueError("event trace has missing or duplicate input polls")
    if not COMMON_EVENTS - {"vi-consumed"} <= {row["event"] for row in rows}:
        raise ValueError("event trace lacks a required controller/update hook")
    return rows


def analyze(native: Path, oracle: Path,
            windows: tuple[tuple[int, int], ...]) -> dict:
    left, right = read(native, windows, "native"), read(oracle, windows, "oracle")
    native_inputs = {row["poll"]: row for row in left
                     if row["event"] == "input-poll"}
    oracle_inputs = {row["poll"]: row for row in right
                     if row["event"] == "input-poll"}
    sample_fields = ("connected", "buttons", "stick_x", "stick_y")
    first_input_mismatch = next((poll for poll in sorted(native_inputs)
                                 if any(native_inputs[poll][field] !=
                                        oracle_inputs[poll][field]
                                        for field in sample_fields)), None)
    first_update_count_mismatch = next((poll for poll in sorted(native_inputs)
                                        if native_inputs[poll]["completed_updates"] !=
                                        oracle_inputs[poll]["completed_updates"]), None)
    per_window = []
    interval_differences = []
    for first, last in windows:
        native_events = [(row["event"], row["poll"]) for row in left
                         if first <= row["poll"] <= last and
                         row["event"] in COMMON_EVENTS]
        oracle_events = [(row["event"], row["poll"]) for row in right
                         if first <= row["poll"] <= last and
                         row["event"] in COMMON_EVENTS]
        mismatch = next((index for index in range(min(len(native_events),
                                                     len(oracle_events)))
                         if native_events[index] != oracle_events[index]), None)
        if mismatch is None and len(native_events) != len(oracle_events):
            mismatch = min(len(native_events), len(oracle_events))
        per_window.append({
            "first_poll": first, "last_poll": last,
            "native_events": len(native_events),
            "oracle_events": len(oracle_events),
            "first_order_difference": None if mismatch is None else {
                "position": mismatch,
                "native": native_events[mismatch] if mismatch < len(native_events)
                else None,
                "oracle": oracle_events[mismatch] if mismatch < len(oracle_events)
                else None,
            },
        })
        for poll in range(first, last):
            def interval(rows):
                samples = [index for index, row in enumerate(rows)
                           if row["event"] == "input-poll" and
                           row["poll"] in (poll, poll + 1)]
                if len(samples) != 2:
                    raise ValueError("event interval lacks adjacent input polls")
                return Counter(row["event"] for row in
                               rows[samples[0] + 1:samples[1]])

            native_interval, oracle_interval = interval(left), interval(right)
            compared = ("vi-consumed", "update-begin", "update-end",
                        "get-entry", "start-entry")
            if any(native_interval[event] != oracle_interval[event]
                   for event in compared):
                interval_differences.append({
                    "after_poll": poll, "before_poll": poll + 1,
                    "native": {event: native_interval[event]
                               for event in compared},
                    "oracle": {event: oracle_interval[event]
                               for event in compared},
                })
    def sha256(path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    return {
        "kind": "jfg-phase9-event-order-diagnostic", "schema": 1,
        "windows": per_window,
        "interval_differences": interval_differences,
        "first_input_mismatch_poll": first_input_mismatch,
        "first_update_count_mismatch_poll": first_update_count_mismatch,
        "native_rows": len(left), "oracle_rows": len(right),
        "native_trace_sha256": sha256(native),
        "oracle_trace_sha256": sha256(oracle),
        "alignment_validated": False, "parity_verified": False,
        "caveat": "Comparable event order does not establish equal initial Pak "
                  "state, within-call input consumption, or VI alignment.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("--window", action="append", required=True,
                        metavar="FIRST:LAST")
    parser.add_argument("--output", type=Path,
                        help="private JSON report; must not already exist")
    args = parser.parse_args()
    try:
        windows = validate_windows(
            [tuple(map(int, value.split(":"))) for value in args.window],
            poll_hashes=True, update_hashes=True)
        report = analyze(args.native, args.oracle, windows)
    except ValueError as error:
        parser.error(str(error))
    encoded = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output is None:
        print(encoded, end="")
    else:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(encoded)


if __name__ == "__main__":
    main()
