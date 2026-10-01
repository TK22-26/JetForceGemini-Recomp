"""Map selected controller polls onto each runtime's VI-consumption clock.

This is a diagnostic join, not proof that the games executed the same guest
instructions between polls. It deliberately never emits a parity verdict.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from scripts.build_phase9_route_replays import load_replay
from scripts.compare_phase9_retrace_hashes import iter_trace, semantic_digest
from scripts.phase95_bridge import digest
from scripts.phase95_poll_compare import native_polls, oracle_polls


def oracle_poll_vi_sequences(path: Path) -> tuple[list[int], int]:
    """Associate every oracle input callback with its preceding consumed VI."""
    sequences: list[int] = []
    consumed = 0
    last_frame = -1
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            parts = line.rstrip("\n").split("\t")
            if parts[0] == "vi-consumed":
                if (len(parts) != 4 or parts[2] != "sequence" or
                        not parts[1].isdecimal() or not parts[3].isdecimal() or
                        int(parts[3]) != consumed + 1 or
                        int(parts[1]) < last_frame):
                    raise ValueError("oracle VI trace is missing or reordered")
                consumed += 1
                last_frame = int(parts[1])
            elif parts[0] == "input-poll":
                if (len(parts) != 14 or parts[2] != "index" or
                        not parts[3].isdecimal() or int(parts[3]) != len(sequences) or
                        not parts[1].isdecimal() or int(parts[1]) < last_frame):
                    raise ValueError("oracle poll cannot be joined to VI sequence")
                sequences.append(consumed)
    if consumed == 0:
        raise ValueError("oracle trace contains no consumed VI events")
    return sequences, consumed


def prefix_hashes(path: Path, highest: int) -> dict[int, str]:
    if highest < 1:
        return {}
    result: dict[int, str] = {}
    stream = iter_trace(path)
    try:
        for record in stream:
            retrace = record["retrace"]
            result[retrace] = semantic_digest(record)
            if retrace >= highest:
                break
    finally:
        stream.close()
    if highest not in result:
        raise ValueError("VI hash trace ends before the requested poll boundary")
    return result


def delta_windows(rows: list[dict[str, Any]]) -> list[dict[str, int]]:
    windows: list[dict[str, int]] = []
    for row in rows:
        delta = row["vi_delta"]
        if windows and windows[-1]["vi_delta"] == delta:
            windows[-1]["last_poll"] = row["poll"]
            windows[-1]["polls"] += 1
        else:
            windows.append({"first_poll": row["poll"], "last_poll": row["poll"],
                            "polls": 1, "vi_delta": delta})
    return windows


def analyze(source: Path, oracle: Path, native: Path, *, max_polls: int = 256,
            output: Path | None = None) -> dict[str, Any]:
    if type(max_polls) is not int or not 1 <= max_polls <= 10_000:
        raise ValueError("max_polls must be 1..10000")
    source, oracle, native = (Path(value).resolve(strict=True)
                              for value in (source, oracle, native))
    if output is not None and output.exists():
        raise FileExistsError(output)
    export = json.loads((source / "export-manifest.json").read_text(encoding="utf-8"))
    input_path = source / "controller.input"
    if (export.get("kind") != "jfg-phase95-selected-input-export" or
            export.get("input_sha256") != digest(input_path)):
        raise ValueError("selected input export identity failed")
    events = load_replay(input_path)
    oracle_result = json.loads((oracle / "oracle-result.json").read_text(encoding="utf-8"))
    native_result = json.loads((native / "native-result.json").read_text(encoding="utf-8"))
    initial = export.get("initial_state") or {}
    if (oracle_result.get("kind") != "jfg-phase95-oracle-poll-replay" or
            native_result.get("kind") != "jfg-phase95-native-selected-poll-replay" or
            not oracle_result.get("trace_complete") or
            not oracle_result.get("vi_consumed_trace_complete") or
            not native_result.get("probe_target_reached") or
            oracle_result.get("input_sha256") != export["input_sha256"] or
            native_result.get("input_sha256") != export["input_sha256"] or
            oracle_result.get("rom_sha256") != native_result.get("rom_sha256") or
            oracle_result.get("oracle_initial_flash_sha256") !=
                initial.get("flash_sha256") or
            native_result.get("initial_flash_sha256") != initial.get("flash_sha256") or
            not oracle_result.get("initial_flash_matches_candidate")):
        raise ValueError("replay identity or initial flash differs")
    o_rows = oracle_polls(oracle / "checkpoints.tsv")
    n_rows = native_polls(native / "controller-polls.tsv")
    o_vi, vi_count = oracle_poll_vi_sequences(oracle / "checkpoints.tsv")
    if (len(o_rows) != len(o_vi) or
            vi_count != oracle_result.get("vi_consumed_count") or
            any(row["poll"] != index for index, row in enumerate(o_rows)) or
            any(row["poll"] != index for index, row in enumerate(n_rows))):
        raise ValueError("poll/VI sequences have gaps or inconsistent counts")
    shared = min(max_polls, len(o_rows), len(n_rows), len(events))
    if shared == 0:
        raise ValueError("no shared controller polls")
    mapped: list[dict[str, Any]] = []
    first_input_mismatch = None
    first_poll_state_mismatch = None
    for index in range(shared):
        o, n, event = o_rows[index], n_rows[index], events[index]
        oracle_vi, native_vi = o_vi[index], n["vi_retrace"]
        row = {"poll": index, "oracle_frame": o["frame"],
               "oracle_vi": oracle_vi, "native_vi": native_vi,
               "vi_delta": oracle_vi - native_vi,
               "oracle_mode": o["mode"], "native_mode": n["front_mode"],
               "oracle_rng": o["rng"], "native_rng": n["rng_seed"]}
        mapped.append(row)
        for system, observed in (("oracle", o), ("native", n)):
            for key, expected in (("buttons", event.buttons),
                                  ("x", event.stick_x), ("y", event.stick_y)):
                if first_input_mismatch is None and observed[key] != expected:
                    first_input_mismatch = {"poll": index, "system": system,
                                            "field": key, "expected": expected,
                                            "observed": observed[key]}
        differences = {name: {"oracle": o[o_key], "native": n[n_key]}
                       for name, o_key, n_key in (
                           ("mode", "mode", "front_mode"),
                           ("level", "level", "level_word"),
                           ("rng", "rng", "rng_seed"))
                       if o[o_key] != n[n_key]}
        if differences and first_poll_state_mismatch is None:
            first_poll_state_mismatch = {"poll": index, "fields": differences}
    o_hashes = prefix_hashes(oracle / "consumed-vi-hashes.jsonl",
                            max(row["oracle_vi"] for row in mapped))
    n_hashes = prefix_hashes(native / "retrace-hashes.jsonl",
                            max(row["native_vi"] for row in mapped))
    hash_comparisons = 0
    hash_matches = 0
    first_hash_mismatch = None
    for row in mapped:
        o_hash, n_hash = o_hashes.get(row["oracle_vi"]), n_hashes.get(row["native_vi"])
        if o_hash is not None and n_hash is not None:
            hash_comparisons += 1
            if o_hash == n_hash:
                hash_matches += 1
            elif first_hash_mismatch is None:
                first_hash_mismatch = {"poll": row["poll"],
                                       "oracle_vi": row["oracle_vi"],
                                       "native_vi": row["native_vi"]}
    windows = delta_windows(mapped)
    frequencies = Counter(row["vi_delta"] for row in mapped)
    report = {
        "kind": "jfg-phase9-poll-vi-alignment", "schema": 1,
        "input_sha256": export["input_sha256"],
        "oracle_vi_hash_sha256": digest(oracle / "consumed-vi-hashes.jsonl"),
        "native_vi_hash_sha256": digest(native / "retrace-hashes.jsonl"),
        "oracle_poll_trace_sha256": digest(oracle / "checkpoints.tsv"),
        "native_poll_trace_sha256": digest(native / "controller-polls.tsv"),
        "initial_flash_match": True, "initial_pak_match": None,
        "shared_polls_analyzed": shared,
        "oracle_vi_count": vi_count,
        "first_input_mismatch": first_input_mismatch,
        "first_poll_state_mismatch": first_poll_state_mismatch,
        "vi_delta_windows": windows[:64],
        "vi_delta_windows_total": len(windows),
        "vi_delta_frequency": [
            {"vi_delta": delta, "polls": count}
            for delta, count in sorted(frequencies.items(), key=lambda item: (-item[1], item[0]))[:16]],
        "poll_preview": mapped[:64],
        "prior_vi_hashes_compared_at_polls": hash_comparisons,
        "prior_vi_hashes_equal_at_polls": hash_matches,
        "first_prior_vi_hash_mismatch": first_hash_mismatch,
        "alignment_validated": False,
        "first_validated_gameplay_divergence": None,
        "limitation": "Same-index polls identify input order, but differing VI schedules and pre-poll hash boundaries do not prove equivalent guest execution points.",
    }
    if output is not None:
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("native", type=Path)
    parser.add_argument("--max-polls", type=int, default=256)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(args.source, args.oracle, args.native,
                     max_polls=args.max_polls, output=args.output)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
