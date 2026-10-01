"""Diagnose a raw update mismatch using a bounded same-poll state anchor.

An anchor is evidence of changed update cadence, not proof that the whole
controller schedule or route is equivalent. Never promote this report to parity.
"""

from __future__ import annotations

import argparse
from itertools import islice
import json
from pathlib import Path

from scripts.compare_phase9_retrace_hashes import semantic_digest
from scripts.compare_phase9_update_hashes import records


def _window(path: Path, first: int, length: int) -> list[dict]:
    stream = records(path)
    try:
        return list(islice(stream, first - 1, first - 1 + length))
    finally:
        stream.close()


def _clock_changes(native: Path, oracle: Path, through: int) -> tuple[int, list[dict]]:
    left, right = records(native), records(oracle)
    changes = []
    count = 0
    previous_delta = None
    previous_native = previous_oracle = None
    try:
        for index, (n, o) in enumerate(zip(left, right), 1):
            if index > through:
                break
            npoll, opoll = n.get("controller_polls"), o.get("controller_polls")
            if type(npoll) is not int or type(opoll) is not int:
                raise ValueError("update stream lacks controller-poll metadata")
            if (previous_native is not None and
                    (npoll < previous_native or opoll < previous_oracle)):
                raise ValueError("controller-poll count regressed between updates")
            delta = opoll - npoll
            if delta != previous_delta:
                count += 1
                if len(changes) < 32:
                    changes.append({
                        "update": index, "native_polls": npoll,
                        "oracle_polls": opoll, "oracle_minus_native": delta,
                        "native_polls_since_prior_update":
                            None if previous_native is None else npoll - previous_native,
                        "oracle_polls_since_prior_update":
                            None if previous_oracle is None else opoll - previous_oracle,
                    })
                previous_delta = delta
            previous_native, previous_oracle = npoll, opoll
            if index == through:
                return count, changes
    finally:
        left.close()
        right.close()
    raise ValueError("declared first mismatch is outside the captured streams")


def _matching_suffix(native: Path, oracle: Path, native_anchor: int,
                     oracle_anchor: int) -> tuple[int, bool, dict | None, dict]:
    left, right = records(native), records(oracle)
    clock = {
        "scope": "offset-paired-updates-diagnostic-only",
        "units": None,
        "metadata_complete": True,
        "delta_mismatch_count": 0,
        "first_delta_mismatch": None,
        "last_delta_mismatches": [],
    }
    try:
        for _ in range(native_anchor - 1):
            if next(left, None) is None:
                raise ValueError("native anchor is outside the captured stream")
        for _ in range(oracle_anchor - 1):
            if next(right, None) is None:
                raise ValueError("oracle anchor is outside the captured stream")
        matched = 0
        previous_native = previous_oracle = None
        oracle_clock_key = None
        while True:
            n = next(left, None)
            if n is None:
                return matched, True, None, clock
            o = next(right, None)
            if o is None:
                return matched, False, {"reason": "oracle-stream-ended",
                                        "native_update": n["update"]}, clock
            if oracle_clock_key is None:
                oracle_clock_key = ("oracle_consumed_vi" if
                                    "oracle_consumed_vi" in o else "emulator_frame")
                clock["units"] = (
                    "native-configured-VI-queue-vs-oracle-configured-VI-queue"
                    if oracle_clock_key == "oracle_consumed_vi" else
                    "native-VI-retraces-versus-oracle-emulator-frames")
            nclock, oclock = n.get("vi_retraces"), o.get(oracle_clock_key)
            if type(nclock) is not int or type(oclock) is not int:
                clock["metadata_complete"] = False
            if (previous_native is not None and previous_oracle is not None and
                    type(nclock) is int and type(oclock) is int):
                ndelta, odelta = nclock - previous_native, oclock - previous_oracle
                if ndelta < 0 or odelta < 0:
                    raise ValueError("update frame/retrace counter regressed")
                if ndelta != odelta:
                    difference = {
                        "native_update": n["update"],
                        "oracle_update": o["update"],
                        "native_vi_since_previous": ndelta,
                        "oracle_clock_since_previous": odelta,
                        "semantic_state_match":
                            semantic_digest(n) == semantic_digest(o),
                    }
                    clock["delta_mismatch_count"] += 1
                    if clock["first_delta_mismatch"] is None:
                        clock["first_delta_mismatch"] = difference
                    clock["last_delta_mismatches"].append(difference)
                    if len(clock["last_delta_mismatches"]) > 16:
                        clock["last_delta_mismatches"].pop(0)
            if semantic_digest(n) != semantic_digest(o):
                return matched, False, {
                    "reason": "semantic-mismatch",
                    "native_update": n["update"], "oracle_update": o["update"],
                    "native_polls": n.get("controller_polls"),
                    "oracle_polls": o.get("controller_polls"),
                    "native_vi_retraces": nclock,
                    "oracle_emulator_frame": o.get("emulator_frame"),
                    "oracle_consumed_vi": o.get("oracle_consumed_vi"),
                    "native_vi_since_previous":
                        nclock - previous_native if previous_native is not None and
                        type(nclock) is int else None,
                    "oracle_clock_since_previous":
                        oclock - previous_oracle if previous_oracle is not None and
                        type(oclock) is int else None,
                }, clock
            matched += 1
            previous_native = nclock if type(nclock) is int else None
            previous_oracle = oclock if type(oclock) is int else None
    finally:
        left.close()
        right.close()


def diagnose(native: Path, oracle: Path, first_update: int, *,
             max_slip: int = 16, minimum_run: int = 8) -> dict:
    if (type(first_update) is not int or first_update < 1 or
            type(max_slip) is not int or not 1 <= max_slip <= 64 or
            type(minimum_run) is not int or not 2 <= minimum_run <= 64):
        raise ValueError("invalid bounded update-alignment limits")
    length = max_slip + minimum_run + 64
    left = _window(native, first_update, length)
    right = _window(oracle, first_update, length)
    if not left or not right or left[0]["update"] != first_update or \
            right[0]["update"] != first_update:
        raise ValueError("first raw mismatch is outside the captured streams")
    for name, stream in (("native", left), ("oracle", right)):
        if any(type(item.get("controller_polls")) is not int for item in stream):
            raise ValueError(f"{name} update stream lacks controller-poll metadata")
    if semantic_digest(left[0]) == semantic_digest(right[0]):
        raise ValueError("declared first raw mismatch is not a semantic mismatch")
    change_count, changes = _clock_changes(native, oracle, first_update)
    report = {
        "kind": "jfg-phase9-update-poll-alignment", "schema": 1,
        "first_raw_mismatch_update": first_update,
        "native_polls_at_mismatch": left[0]["controller_polls"],
        "oracle_polls_at_mismatch": right[0]["controller_polls"],
        "classification": "unresolved-update-mismatch",
        "same_poll_anchor": None, "matched_update_run": 0,
        "native_suffix_exhausted": False, "first_later_mismatch": None,
        "paired_update_clock": None,
        "clock_delta_change_count": change_count,
        "first_clock_delta_changes": changes,
        "alignment_validated": False, "parity_verified": False,
    }
    left_digests = [semantic_digest(item) for item in left]
    right_digests = [semantic_digest(item) for item in right]
    candidates = []
    for i in range(min(max_slip + 1, len(left))):
        for j in range(min(max_slip + 1, len(right))):
            if (i == 0 and j == 0) or \
                    left[i]["controller_polls"] != right[j]["controller_polls"] or \
                    left_digests[i] != right_digests[j]:
                continue
            run = 0
            while (i + run < len(left) and j + run < len(right) and
                   left_digests[i + run] == right_digests[j + run]):
                run += 1
            if run >= minimum_run:
                candidates.append((-(run), i + j, i, j))
    if candidates:
        _, _, i, j = min(candidates)
        run, exhausted, later, clock = _matching_suffix(
            native, oracle, left[i]["update"], right[j]["update"])
        report["classification"] = "poll-anchored-semantic-resynchronization"
        report["same_poll_anchor"] = {
            "native_update": left[i]["update"],
            "oracle_update": right[j]["update"],
            "controller_polls": left[i]["controller_polls"],
            "native_vi_retraces": left[i].get("vi_retraces"),
            "oracle_emulator_frame": right[j].get("emulator_frame"),
            "oracle_consumed_vi": right[j].get("oracle_consumed_vi"),
        }
        report["matched_update_run"] = run
        report["native_suffix_exhausted"] = exhausted
        report["first_later_mismatch"] = later
        report["paired_update_clock"] = clock
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("--first-update", type=int, required=True)
    parser.add_argument("--max-slip", type=int, default=16)
    parser.add_argument("--minimum-run", type=int, default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = diagnose(args.native, args.oracle, args.first_update,
                      max_slip=args.max_slip, minimum_run=args.minimum_run)
    rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
