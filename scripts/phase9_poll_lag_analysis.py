"""Find exact nearby state recurrences around unaligned controller polls.

This is a cadence diagnostic, not proof that shifted polls consume equivalent
inputs or that the native and oracle observation hooks are aligned.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import tempfile

from scripts.compare_phase9_poll_hashes import STATE_FIELDS, compare, records
from scripts.phase95_bridge import digest


KIND = "jfg-phase9-poll-lag-analysis"
MAX_POLLS = 10_000


def _rows(path: Path, side: str, count: int) -> list[dict]:
    stream = records(path, side)
    try:
        rows = list(islice(stream, count))
    finally:
        stream.close()
    if len(rows) != count:
        raise ValueError(f"incomplete {side} poll-state prefix")
    return rows


def _state_key(row: dict) -> bytes:
    state = [row[field] for field in STATE_FIELDS]
    return hashlib.sha256(json.dumps(
        state, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).digest()


def analyze(source: Path, native: Path, oracle: Path, comparison_path: Path,
            *, radius: int = 8) -> dict:
    source, native, oracle, comparison_path = (
        Path(value).resolve(strict=True) for value in
        (source, native, oracle, comparison_path))
    if type(radius) is not int or not 1 <= radius <= 32:
        raise ValueError("poll lag radius must be 1..32")
    stored = json.loads(comparison_path.read_text(encoding="utf-8"))
    if (not isinstance(stored, dict) or
            type(stored.get("requested_polls")) is not int or
            not 1 <= stored["requested_polls"] <= MAX_POLLS):
        raise ValueError("poll comparison exceeds the bounded analysis prefix")
    count = stored["requested_polls"]
    fresh = compare(source, native, oracle, prefix_polls=count)
    if stored != fresh or (fresh["producer_provenance"].get("verified") is not True or
                           fresh["input_prefix_match"] is not True or
                           fresh["state_scan_complete"] is not True):
        raise ValueError("poll comparison is incomplete or changed")
    left = _rows(native, "native", count)
    right = _rows(oracle, "oracle", count)
    left_keys = [_state_key(row) for row in left]
    right_keys = [_state_key(row) for row in right]
    outcomes = Counter()
    unique_offsets = Counter()
    unique_input_matches = 0
    examples = []
    unmatched = []
    window_details = []
    mismatch_start = None
    window_outcomes = Counter()

    def close_window(last: int) -> None:
        nonlocal mismatch_start, window_outcomes
        if mismatch_start is not None:
            window_details.append({
                "first_poll": mismatch_start, "last_poll": last,
                "unique_shift_match": window_outcomes["unique"],
                "ambiguous_shift_match": window_outcomes["ambiguous"],
                "no_shift_match": window_outcomes["none"],
            })
            mismatch_start = None
            window_outcomes = Counter()

    for poll in range(count):
        same = (left_keys[poll] == right_keys[poll] and
                all(left[poll][field] == right[poll][field]
                    for field in STATE_FIELDS))
        if same:
            close_window(poll - 1)
            continue
        if mismatch_start is None:
            mismatch_start = poll
        matches = [other for other in range(
            max(0, poll - radius), min(count, poll + radius + 1))
            if other != poll and left_keys[poll] == right_keys[other] and
            all(left[poll][field] == right[other][field]
                for field in STATE_FIELDS)]
        outcome = "unique" if len(matches) == 1 else (
            "ambiguous" if matches else "none")
        outcomes[outcome] += 1
        window_outcomes[outcome] += 1
        if outcome == "unique":
            unique_offsets[matches[0] - poll] += 1
            unique_input_matches += all(
                left[poll][key] == right[matches[0]][key]
                for key in ("connected", "buttons", "stick_x", "stick_y"))
        elif outcome == "none" and len(unmatched) < 32:
            unmatched.append(poll)
        if len(examples) < 16:
            examples.append({
                "native_poll": poll, "candidate_oracle_polls": matches,
                "outcome": outcome,
                "native_completed_updates": left[poll]["completed_updates"],
                "same_poll_oracle_completed_updates":
                    right[poll]["completed_updates"],
            })
    close_window(count - 1)
    if (sum(outcomes.values()) != fresh["mismatching_polls"] or
            len(window_details) != fresh["mismatch_windows"] or
            ([
                (item["first_poll"], item["last_poll"])
                for item in window_details[:8]] != [
                (item["first_poll"], item["last_poll"])
                for item in fresh["first_mismatch_windows"]])):
        raise ValueError("lag scan disagrees with the pinned poll comparison")
    return {
        "kind": KIND, "schema": 1, "acceptance": False,
        "alignment_validated": False, "parity_verified": False,
        "comparison_sha256": digest(comparison_path),
        "native_trace_sha256": digest(native),
        "oracle_trace_sha256": digest(oracle),
        "compared_polls": count, "search_radius_polls": radius,
        "mismatching_polls": sum(outcomes.values()),
        "unique_shift_match": outcomes["unique"],
        "ambiguous_shift_match": outcomes["ambiguous"],
        "no_shift_match": outcomes["none"],
        "unique_shift_input_values_match": unique_input_matches,
        "unique_shift_offsets": {
            str(offset): unique_offsets[offset] for offset in sorted(unique_offsets)},
        "first_unmatched_polls": unmatched,
        "first_mismatch_examples": examples,
        "mismatch_windows": window_details,
        "caveat": "Exact nearby state recurrence is diagnostic only; shifted input polls and hook phases are not validated as equivalent.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("native", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("--radius", type=int, default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(args.source, args.native, args.oracle, args.comparison,
                     radius=args.radius)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        path = args.output.resolve()
        if path.exists():
            if path.read_text(encoding="utf-8") != rendered:
                parser.error("existing lag report differs")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", dir=path.parent,
                    prefix=f".{path.name}.", suffix=".tmp",
                    delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(rendered)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
    print(rendered, end="")


if __name__ == "__main__":
    main()
