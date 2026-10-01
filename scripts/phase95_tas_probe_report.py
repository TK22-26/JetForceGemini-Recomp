"""Summarize raw Japanese TAS RAM-probe changes without assigning game meanings.

Capture files and this report belong in ignored private storage. A changed value
is only a candidate milestone; Japanese field semantics require independent
validation before the frontier graph may call it a level or objective.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SCHEMA = "jfg-phase95-jp-raw-probe-report-v1"
PINS = ("rom_sha1", "rom_sha256", "movie_sha256", "movie_frames",
        "emulator_sha256", "runtime_sha256", "script_sha256")
RAW_COLUMNS = ("raw_0xA51B0_u8", "raw_0xFB114_u32be",
               "raw_0xA33E4_u32be", "raw_0x1BD150_u32be")


def summarize(segments: list[Path], *, event_limit: int = 10_000) -> dict:
    """Require complete, contiguous, pinned segments; emit bounded change lists."""
    if not segments or not 0 <= event_limit <= 100_000:
        raise ValueError("provide segments and a bounded event limit")
    expected = None
    first = None
    next_frame = None
    previous_directory = None
    previous_state_hash = None
    lineage_verified = True
    last_values = {}
    changes = {column: {"count": 0, "events": [], "first_value": None,
                        "last_value": None} for column in RAW_COLUMNS}
    segment_info = []
    for directory in map(Path, segments):
        result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
        if result.get("complete") is not True or result.get("semantic_status") != "raw-unverified-jp":
            raise ValueError(f"incomplete or semantic-status mismatch: {directory}")
        identity = {key: result.get(key) for key in PINS}
        if any(value is None for value in identity.values()):
            raise ValueError(f"missing source pin: {directory}")
        if expected is None:
            expected = identity
            first = result["first"]
            next_frame = first
            lineage_verified = first == 0
            if first == 0 and (result.get("resume_from") is not None or
                               result.get("parent_continuation_sha256") is not None):
                raise ValueError(f"fresh segment has a resume parent: {directory}")
        if identity != expected or result["first"] != next_frame or result["last"] < next_frame:
            raise ValueError(f"pin mismatch or noncontiguous segment: {directory}")
        if previous_directory is not None:
            recorded_parent = result.get("resume_from")
            recorded_hash = result.get("parent_continuation_sha256")
            if recorded_parent is not None and \
                    Path(recorded_parent).resolve() != previous_directory.resolve():
                raise ValueError(f"resume source mismatch: {directory}")
            if recorded_hash is not None and recorded_hash != previous_state_hash:
                raise ValueError(f"parent state hash mismatch: {directory}")
            if recorded_parent is None or recorded_hash is None:
                lineage_verified = False
        trace = directory / "frames.tsv"
        with trace.open(encoding="utf-8") as stream:
            if stream.readline() != "schema\t1\n" or stream.readline() != "probe_status\tunverified-jp\n":
                raise ValueError(f"invalid raw trace header: {trace}")
            columns = stream.readline().rstrip("\n").split("\t")
            if columns[:3] != ["frame", "movie_mode", "input_polls_since_worker_start"] or \
                    not all(column in columns for column in RAW_COLUMNS):
                raise ValueError(f"unexpected raw trace columns: {trace}")
            positions = {column: columns.index(column) for column in RAW_COLUMNS}
            for row in stream:
                values = row.rstrip("\n").split("\t")
                if len(values) != len(columns) or int(values[0]) != next_frame or \
                        values[1] not in ("PLAY", "FINISHED"):
                    raise ValueError(f"missing or malformed trace frame: {trace}")
                for column in RAW_COLUMNS:
                    value = values[positions[column]]
                    if not value or any(char not in "0123456789ABCDEF" for char in value):
                        raise ValueError(f"invalid raw hex value: {trace}")
                    before = last_values.get(column)
                    if changes[column]["first_value"] is None:
                        changes[column]["first_value"] = value
                    if before is not None and value != before:
                        item = changes[column]
                        item["count"] += 1
                        if len(item["events"]) < event_limit:
                            item["events"].append({"frame": next_frame,
                                                   "before": before, "after": value})
                    last_values[column] = value
                    changes[column]["last_value"] = value
                next_frame += 1
        if next_frame != result["last"] + 1:
            raise ValueError(f"trace does not end at declared frame: {trace}")
        segment_info.append({"first": result["first"], "last": result["last"],
                             "captured_frames": result.get("captured_frames")})
        previous_directory = directory
        previous_state_hash = result.get("continuation_sha256")
    for item in changes.values():
        item["truncated"] = item["count"] > len(item["events"])
    return {"schema": SCHEMA, "semantic_status": "raw-unverified-jp",
            "acceptance": False, "identity": expected,
            "lineage_verified": lineage_verified,
            "first": first, "last": next_frame - 1,
            "segments": segment_info, "changes": changes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segments", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--event-limit", type=int, default=10_000)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    result = summarize(args.segments, event_limit=args.event_limit)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(f"raw capture frames {result['first']}..{result['last']}; "
          f"probe change counts: " + ", ".join(
              f"{key}={value['count']}" for key, value in result["changes"].items()))


if __name__ == "__main__":
    main()
