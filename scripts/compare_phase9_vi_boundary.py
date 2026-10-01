"""Compare bounded VI-consumption windows around a focused update mismatch.

The native and oracle hooks have not been proved to be equivalent execution
boundaries. This report is diagnostic evidence, never a parity result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.compare_phase9_focus_rdram import _record_at, compare as compare_focus
from scripts.compare_phase9_retrace_hashes import (
    describe_difference, iter_trace, semantic_digest,
)


MAX_INTERVAL = 64


def _vi_records(path: Path, start: int, end: int) -> list[dict]:
    if (type(start) is not int or type(end) is not int or
            start < 0 or end <= start or end - start > MAX_INTERVAL):
        raise ValueError("VI interval is invalid or exceeds diagnostic bound")
    stream = iter_trace(path)
    try:
        selected = [item for item in stream if start < item["retrace"] <= end]
    finally:
        stream.close()
    if len(selected) != end - start:
        raise ValueError(f"VI trace is incomplete in interval {start}..{end}")
    return selected


def _pair_interval(native: list[dict], oracle: list[dict]) -> dict:
    paired = []
    first_mismatch = None
    for index, (left, right) in enumerate(zip(native, oracle), 1):
        matching = semantic_digest(left) == semantic_digest(right)
        components, actors = ([], []) if matching else describe_difference(left, right)
        item = {
            "relative_consumption": index,
            "native_vi": left["retrace"],
            "oracle_vi": right["retrace"],
            "semantic_state_match": matching,
            "components": components,
            "actor_difference_count": len(actors),
            "native_rng_seed": left["rng_seed"],
            "oracle_rng_seed": right["rng_seed"],
        }
        paired.append(item)
        if not matching and first_mismatch is None:
            first_mismatch = item
    return {
        "native_consumptions": len(native),
        "oracle_consumptions": len(oracle),
        "first_relative_mismatch": first_mismatch,
        "paired_consumptions": paired,
        "extra_native_vi": [item["retrace"] for item in native[len(paired):]],
        "extra_oracle_vi": [item["retrace"] for item in oracle[len(paired):]],
    }


def compare(native_dir: Path, oracle_dir: Path, *, native_before: int,
            oracle_before: int, native_after: int, oracle_after: int) -> dict:
    native_dir, oracle_dir = Path(native_dir), Path(oracle_dir)
    if native_before < 2 or oracle_before < 2:
        raise ValueError("VI boundary comparison requires a prior update")
    focused = compare_focus(native_dir, oracle_dir,
                            native_before=native_before,
                            oracle_before=oracle_before,
                            native_after=native_after,
                            oracle_after=oracle_after)
    if (focused["before"]["semantic_state_match"] is not True or
            focused["after"]["semantic_state_match"] is not False or
            focused["vi_consumption_between"]["oracle_counter_available"] is not True):
        raise ValueError("focused pair does not establish the requested onset")
    native_trace = native_dir / "retrace-hashes.jsonl.updates.jsonl"
    oracle_trace = oracle_dir / "update-hashes.jsonl"
    n_prev = _record_at(native_trace, native_before - 1)
    n_before = _record_at(native_trace, native_before)
    n_after = _record_at(native_trace, native_after)
    o_prev = _record_at(oracle_trace, oracle_before - 1)
    o_before = _record_at(oracle_trace, oracle_before)
    o_after = _record_at(oracle_trace, oracle_after)
    native_vi = native_dir / "retrace-hashes.jsonl"
    oracle_vi = oracle_dir / "consumed-vi-hashes.jsonl"
    if not oracle_vi.is_file():
        raise ValueError("oracle configured-VI trace is missing")
    for record in (o_prev, o_before, o_after):
        if type(record.get("oracle_consumed_vi")) is not int:
            raise ValueError("oracle update lacks configured-VI counter")
    lead_in = _pair_interval(
        _vi_records(native_vi, n_prev["vi_retraces"], n_before["vi_retraces"]),
        _vi_records(oracle_vi, o_prev["oracle_consumed_vi"],
                    o_before["oracle_consumed_vi"]))
    onset = _pair_interval(
        _vi_records(native_vi, n_before["vi_retraces"], n_after["vi_retraces"]),
        _vi_records(oracle_vi, o_before["oracle_consumed_vi"],
                    o_after["oracle_consumed_vi"]))
    return {
        "kind": "jfg-phase9-vi-boundary-comparison", "schema": 1,
        "source_export": focused["source_export"],
        "input_sha256": focused["input_sha256"],
        "rom_sha256": focused["rom_sha256"],
        "focused_update_pair": {
            "native_before": native_before, "oracle_before": oracle_before,
            "native_after": native_after, "oracle_after": oracle_after,
        },
        "lead_in": lead_in,
        "onset": onset,
        "hook_equivalence": "unvalidated",
        "alignment_validated": False,
        "parity_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_dir", type=Path)
    parser.add_argument("oracle_dir", type=Path)
    parser.add_argument("--native-before", type=int, required=True)
    parser.add_argument("--oracle-before", type=int, required=True)
    parser.add_argument("--native-after", type=int, required=True)
    parser.add_argument("--oracle-after", type=int, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare(args.native_dir, args.oracle_dir,
                     native_before=args.native_before,
                     oracle_before=args.oracle_before,
                     native_after=args.native_after,
                     oracle_after=args.oracle_after)
    rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
