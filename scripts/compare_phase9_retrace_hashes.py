#!/usr/bin/env python3
"""Find the first semantic divergence between native and BizHawk traces."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator


HEADER_KIND = "jfg-phase9-retrace-hash-header"
RECORD_KIND = "jfg-phase9-retrace-hash"
SCHEMA = 1


def validate_state(record: dict[str, Any]) -> None:
    for field in ("front_mode", "actor_count"):
        if type(record.get(field)) is not int or record[field] < 0:
            fail(f"invalid or missing {field}")
    for field in ("rng_seed", "player_actor", "actor_list"):
        if not isinstance(record.get(field), str) or not re.fullmatch(
            r"0x[0-9a-fA-F]{8}", record[field]
        ):
            fail(f"invalid or missing {field}")
    for field in ("player_sha256", "actor_table_sha256", "globals_sha256",
                  "camera_sha256"):
        if field not in record:
            fail(f"missing {field}")
        value = record[field]
        if value is not None and (not isinstance(value, str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}", value
        )):
            fail(f"invalid {field}")
    actor_map(record)


def fail(message: str) -> None:
    raise ValueError(message)


def iter_trace(path: Path, offset: int = 0) -> Iterator[dict[str, Any]]:
    """Validate and yield one retrace at a time, including large routes."""
    previous_retrace: int | None = None
    with path.open("r", encoding="utf-8") as stream:
        try:
            header = json.loads(next(stream))
        except StopIteration:
            fail(f"empty trace: {path}")
        if header != {"kind": HEADER_KIND, "schema": SCHEMA}:
            fail(f"invalid trace header: {path}")
        for line_number, line in enumerate(stream, 2):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                fail(f"invalid JSON at {path}:{line_number}: {error}")
            if not isinstance(record, dict) or record.get("kind") != RECORD_KIND or record.get("schema") != SCHEMA:
                fail(f"invalid record at {path}:{line_number}")
            retrace = record.get("retrace")
            if type(retrace) is not int or retrace < 0:
                fail(f"invalid retrace at {path}:{line_number}")
            if previous_retrace is not None and retrace != previous_retrace + 1:
                fail(f"non-contiguous retrace at {path}:{line_number}: "
                     f"expected {previous_retrace + 1}, got {retrace}")
            previous_retrace = retrace
            try:
                validate_state(record)
            except ValueError as error:
                fail(f"invalid state at {path}:{line_number}: {error}")
            retrace += offset
            record = dict(record)
            record["retrace"] = retrace
            yield record
    if previous_retrace is None:
        fail(f"trace contains no records: {path}")


def load_trace(path: Path, offset: int = 0) -> dict[int, dict[str, Any]]:
    """Materialize a trace for callers that need random access."""
    return {record["retrace"]: record for record in iter_trace(path, offset)}


def semantic_digest(record: dict[str, Any]) -> str:
    payload = {key: value for key, value in record.items()
               if key not in {"kind", "schema", "retrace", "update",
                              "controller_polls", "vi_retraces", "emulator_frame",
                              "oracle_consumed_vi"}}
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def actor_map(record: dict[str, Any]) -> dict[int, dict[str, Any]]:
    actors = record.get("actors")
    if not isinstance(actors, list):
        fail("actors must be a list")
    result: dict[int, dict[str, Any]] = {}
    for actor in actors:
        if (not isinstance(actor, dict) or type(actor.get("index")) is not int
                or actor["index"] < 0):
            fail("invalid actor record")
        if not isinstance(actor.get("address"), str) or not re.fullmatch(
            r"0x[0-9a-fA-F]{8}", actor["address"]
        ):
            fail("invalid or missing actor address")
        if "sha256" not in actor:
            fail("missing actor sha256")
        digest = actor["sha256"]
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}", digest
        )):
            fail("invalid actor sha256")
        index = actor["index"]
        if index in result:
            fail(f"duplicate actor index {index}")
        result[index] = actor
    return result


def describe_difference(
    native: dict[str, Any], oracle: dict[str, Any]
) -> tuple[list[str], list[dict[str, Any]]]:
    fields = [
        "front_mode", "rng_seed", "player_actor", "player_sha256",
        "actor_list", "actor_count", "actor_table_sha256",
        "globals_sha256", "camera_sha256",
    ]
    components = [field for field in fields if native.get(field) != oracle.get(field)]
    native_actors = actor_map(native)
    oracle_actors = actor_map(oracle)
    actor_differences: list[dict[str, Any]] = []
    for index in sorted(native_actors.keys() | oracle_actors.keys()):
        native_actor = native_actors.get(index)
        oracle_actor = oracle_actors.get(index)
        if native_actor != oracle_actor:
            actor_differences.append({
                "index": index,
                "native": native_actor,
                "oracle": oracle_actor,
            })
    if actor_differences:
        components.append("actors")
    return components, actor_differences


def compare(
    native_path: Path, oracle_path: Path, oracle_offset: int
) -> tuple[dict[str, Any], bool]:
    native_stream = iter(iter_trace(native_path))
    oracle_stream = iter(iter_trace(oracle_path, oracle_offset))
    native = next(native_stream, None)
    oracle = next(oracle_stream, None)
    native_only_first = None
    oracle_only_first = None
    common_count = 0
    first_divergence = None
    first_divergence_count = None
    final_digest = None
    while native is not None or oracle is not None:
        if native is not None and (oracle is None or native["retrace"] < oracle["retrace"]):
            if native_only_first is None:
                native_only_first = native["retrace"]
            native = next(native_stream, None)
            continue
        if oracle is not None and (native is None or oracle["retrace"] < native["retrace"]):
            if oracle_only_first is None:
                oracle_only_first = oracle["retrace"]
            oracle = next(oracle_stream, None)
            continue
        assert native is not None and oracle is not None
        common_count += 1
        if first_divergence is None:
            native_digest = semantic_digest(native)
            oracle_digest = semantic_digest(oracle)
            if native_digest != oracle_digest:
                components, actors = describe_difference(native, oracle)
                first_divergence = {
                    "retrace": native["retrace"],
                    "native_sha256": native_digest,
                    "oracle_sha256": oracle_digest,
                    "components": components,
                    "actor_differences": actors,
                }
                first_divergence_count = common_count
            else:
                final_digest = native_digest
        native = next(native_stream, None)
        oracle = next(oracle_stream, None)
    if common_count == 0:
        fail("traces have no common retraces")
    if first_divergence is not None:
        return ({
            "kind": "jfg-phase9-retrace-comparison",
            "schema": 1,
            "match": False,
            "compared_retraces": first_divergence_count,
            "first_divergence": first_divergence,
            "native_only_first": native_only_first,
            "oracle_only_first": oracle_only_first,
        }, False)
    match = native_only_first is None and oracle_only_first is None
    return ({
        "kind": "jfg-phase9-retrace-comparison",
        "schema": 1,
        "match": match,
        "compared_retraces": common_count,
        "first_divergence": None,
        "native_only_first": native_only_first,
        "oracle_only_first": oracle_only_first,
        "final_sha256": final_digest,
    }, match)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("native", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("--oracle-offset", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report, match = compare(args.native, args.oracle, args.oracle_offset)
    except (OSError, ValueError) as error:
        print(f"retrace comparison failed: {error}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0 if match else 1


if __name__ == "__main__":
    raise SystemExit(main())
