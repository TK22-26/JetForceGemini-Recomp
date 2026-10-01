"""Compare controller-call phase at native and BizHawk poll snapshots.

This is a diagnostic of hook ordering, not proof of equivalent sampling or
initial controller-accessory state. It accepts poll traces with new call-count
fields and deliberately does not change the version-1 semantic comparator.
"""

from __future__ import annotations

import argparse
from collections import Counter
from itertools import islice
import json
from pathlib import Path

from scripts.compare_phase9_poll_hashes import records
from scripts.phase95_bridge import digest


FIELDS = ("controller_read_start_calls", "controller_get_data_calls")


def analyze(native: Path, oracle: Path, *, prefix_polls: int | None = None) -> dict:
    native, oracle = Path(native), Path(oracle)
    if prefix_polls is not None and (type(prefix_polls) is not int or
                                     prefix_polls < 1):
        raise ValueError("prefix_polls must be positive")
    native_rows = records(native, "native")
    oracle_rows = records(oracle, "oracle")
    if prefix_polls is not None:
        native_rows = islice(native_rows, prefix_polls)
        oracle_rows = islice(oracle_rows, prefix_polls)
    offsets = Counter()
    first_difference = None
    previous = {"native": None, "oracle": None}
    last = {"native": None, "oracle": None}
    count = 0
    for left, right in zip(native_rows, oracle_rows, strict=True):
        if left["poll"] != right["poll"]:
            raise ValueError("native and oracle poll indices differ")
        for side, row in (("native", left), ("oracle", right)):
            values = tuple(row.get(field) for field in FIELDS)
            if any(type(value) is not int or value < 0 for value in values):
                raise ValueError(f"{side} poll {row['poll']} lacks call-phase counters")
            if previous[side] is not None and any(
                    value < prior for value, prior in zip(values, previous[side])):
                raise ValueError(f"{side} call-phase counters decreased")
            previous[side] = values
            last[side] = values
        left_values = last["native"]
        right_values = last["oracle"]
        offsets[(left_values[0] - right_values[0],
                 left_values[1] - right_values[1])] += 1
        if left_values != right_values and first_difference is None:
            first_difference = {"poll": left["poll"],
                                "native": dict(zip(FIELDS, left_values)),
                                "oracle": dict(zip(FIELDS, right_values))}
        count += 1
    if count == 0:
        raise ValueError("no controller polls compared")
    if prefix_polls is not None and count != prefix_polls:
        raise ValueError("fewer poll rows than requested prefix")
    return {
        "kind": "jfg-phase9-poll-call-phase", "schema": 1,
        "native_sha256": digest(native), "oracle_sha256": digest(oracle),
        "polls_compared": count,
        "prefix_polls": prefix_polls,
        "hooks_observed": all(value > 0 for values in last.values()
                              for value in values),
        "same_call_phase": first_difference is None,
        "first_call_phase_difference": first_difference,
        "offset_counts": [
            {"native_minus_oracle_start": start,
             "native_minus_oracle_get": get, "polls": occurrences}
            for (start, get), occurrences in sorted(offsets.items())],
        "alignment_validated": False, "parity_verified": False,
        "caveat": "Call counts do not prove identical within-call sampling, "
                  "initial Pak state, or semantic parity.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("--prefix-polls", type=int)
    args = parser.parse_args()
    print(json.dumps(analyze(args.native, args.oracle,
                             prefix_polls=args.prefix_polls), sort_keys=True))


if __name__ == "__main__":
    main()
