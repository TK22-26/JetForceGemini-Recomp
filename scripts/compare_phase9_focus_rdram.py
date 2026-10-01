"""Compare canonical actor bytes in two focused completed-update captures."""

from __future__ import annotations

import argparse
from bisect import bisect_right
import hashlib
from itertools import islice
import json
from pathlib import Path

from scripts.compare_phase9_retrace_hashes import semantic_digest
from scripts.compare_phase9_update_hashes import records
from scripts.build_phase9_route_replays import load_replay


RDRAM_BYTES = 4 * 1024 * 1024
ACTOR_BYTES = 0x200


def _records_at(path: Path, updates) -> dict[int, dict]:
    """Validate the prefix once per call; retain only requested records.

    No cache survives this call: a later evidence recheck rereads the file.
    The ordinary records parser still validates every intervening update.
    """
    requested = tuple(updates)
    if not requested or any(type(value) is not int or value < 1 for value in requested):
        raise ValueError("requested updates must be positive integers")
    wanted = set(requested)
    selected = {}
    stream = records(path)
    try:
        for record in islice(stream, max(wanted)):
            if record["update"] in wanted:
                selected[record["update"]] = record
    finally:
        stream.close()
    missing = wanted - selected.keys()
    if missing:
        raise ValueError(f"update {min(missing)} is missing from {path}")
    return selected


def _record_at(path: Path, update: int) -> dict:
    return _records_at(path, (update,))[update]


def _snapshot(directory: Path, record: dict) -> tuple[bytes, str]:
    path = directory / f"focus-update-{record['update']}.rdram"
    data = path.read_bytes()
    if len(data) != RDRAM_BYTES:
        raise ValueError(f"focused RDRAM size is invalid: {path}")
    for actor in record["actors"]:
        address = int(actor["address"], 16) & 0x1FFFFFFF
        if address == 0 or address + ACTOR_BYTES > len(data):
            raise ValueError(f"actor address is outside focused RDRAM: {path}")
        expected = actor["sha256"]
        if expected != hashlib.sha256(data[address:address + ACTOR_BYTES]).hexdigest():
            raise ValueError(f"focused actor bytes do not match update trace: {path}")
    return data, hashlib.sha256(data).hexdigest()


def _actor_differences(native: bytes, oracle: bytes, native_record: dict,
                       oracle_record: dict) -> list[dict]:
    left, right = native_record["actors"], oracle_record["actors"]
    if (len(left) != len(right) or
            any(a["address"] != b["address"] or a["index"] != b["index"]
                for a, b in zip(left, right))):
        raise ValueError("actor layout differs at focused update pair")
    differences = []
    for actor in left:
        base = int(actor["address"], 16) & 0x1FFFFFFF
        offsets = [index for index in range(ACTOR_BYTES)
                   if native[base + index] != oracle[base + index]]
        if offsets:
            differences.append({
                "index": actor["index"], "address": actor["address"],
                "differing_bytes": len(offsets), "first_offsets": offsets[:16],
            })
    return differences


def _input_between(events, starts: list[int], before: dict,
                   after: dict) -> list[dict]:
    first, last = before.get("controller_polls"), after.get("controller_polls")
    if (type(first) is not int or type(last) is not int or
            first < 0 or not first <= last or last - first > 64):
        raise ValueError("invalid focused controller-poll interval")
    samples = []
    for poll in range(first, last):
        location = bisect_right(starts, poll) - 1
        if location < 0 or poll >= events[location].last:
            raise ValueError(f"selected input is missing poll {poll}")
        event = events[location]
        samples.append({"poll": poll, "connected": event.connected,
                        "buttons": f"{event.buttons:04x}",
                        "stick_x": event.stick_x, "stick_y": event.stick_y})
    return samples


def compare(native_dir: Path, oracle_dir: Path, *, native_before: int,
            oracle_before: int, native_after: int, oracle_after: int) -> dict:
    native_dir, oracle_dir = Path(native_dir), Path(oracle_dir)
    if any(type(value) is not int or value < 1 for value in (
            native_before, oracle_before, native_after, oracle_after)) or \
            native_after <= native_before or oracle_after <= oracle_before:
        raise ValueError("invalid focused update pair")
    n_result = json.loads((native_dir / "native-result.json").read_text(encoding="utf-8"))
    o_result = json.loads((oracle_dir / "oracle-result.json").read_text(encoding="utf-8"))
    if (n_result.get("probe_target_reached") is not True or
            o_result.get("trace_complete") is not True or
            n_result.get("focused_update_capture_complete") is not True or
            o_result.get("focused_update_capture_complete") is not True or
            n_result.get("source_export") != o_result.get("source_export") or
            n_result.get("input_sha256") != o_result.get("input_sha256") or
            n_result.get("rom_sha256") != o_result.get("rom_sha256") or
            n_result.get("initial_flash_sha256") !=
                o_result.get("oracle_initial_flash_sha256")):
        raise ValueError("focused captures do not share verified replay provenance")
    input_path = Path(n_result["source_export"]) / "controller.input"
    if hashlib.sha256(input_path.read_bytes()).hexdigest() != n_result["input_sha256"]:
        raise ValueError("focused selected input differs from pinned replay")
    events = load_replay(input_path)
    starts = [event.first for event in events]
    for result, first, last in ((n_result, native_before, native_after),
                                (o_result, oracle_before, oracle_after)):
        focus = result.get("focused_update_range")
        if (not isinstance(focus, list) or len(focus) != 2 or
                focus[0] > first or focus[1] < last):
            raise ValueError("focused update pair is outside declared capture")
    n_trace = native_dir / "retrace-hashes.jsonl.updates.jsonl"
    o_trace = oracle_dir / "update-hashes.jsonl"
    before_n = _record_at(n_trace, native_before)
    before_o = _record_at(o_trace, oracle_before)
    after_n = _record_at(n_trace, native_after)
    after_o = _record_at(o_trace, oracle_after)
    n0, n0_hash = _snapshot(native_dir, before_n)
    o0, o0_hash = _snapshot(oracle_dir, before_o)
    n1, n1_hash = _snapshot(native_dir, after_n)
    o1, o1_hash = _snapshot(oracle_dir, after_o)
    before_differences = _actor_differences(n0, o0, before_n, before_o)
    after_differences = _actor_differences(n1, o1, after_n, after_o)
    native_samples = _input_between(events, starts, before_n, after_n)
    oracle_samples = _input_between(events, starts, before_o, after_o)
    oracle_vi_before = before_o.get("oracle_consumed_vi")
    oracle_vi_after = after_o.get("oracle_consumed_vi")
    vi_counter_available = (type(oracle_vi_before) is int and
                            type(oracle_vi_after) is int)
    if (type(before_n.get("vi_retraces")) is not int or
            type(after_n.get("vi_retraces")) is not int or
            after_n["vi_retraces"] < before_n["vi_retraces"]):
        raise ValueError("native VI consumption is missing or regressed")
    if vi_counter_available and oracle_vi_after < oracle_vi_before:
        raise ValueError("oracle VI consumption regressed in focused pair")
    vi_consumption = {
        "scope": "configured-VI-queue-counters-diagnostic-only",
        "oracle_counter_available": vi_counter_available,
        "native_between": after_n["vi_retraces"] - before_n["vi_retraces"],
        "oracle_between": oracle_vi_after - oracle_vi_before
            if vi_counter_available else None,
    }
    vi_consumption["same_count"] = (
        vi_consumption["native_between"] == vi_consumption["oracle_between"]
        if vi_counter_available else None)
    def values(samples: list[dict]) -> list[tuple]:
        return [(item["connected"], item["buttons"], item["stick_x"],
                 item["stick_y"]) for item in samples]
    return {
        "kind": "jfg-phase9-focus-rdram-comparison", "schema": 1,
        "source_export": n_result["source_export"],
        "input_sha256": n_result["input_sha256"],
        "rom_sha256": n_result["rom_sha256"],
        "initial_flash_matches_both": True,
        "oracle_pak_equivalence": "not_verified",
        "controller_inputs_between": {
            "native": native_samples, "oracle": oracle_samples,
            "same_values": values(native_samples) == values(oracle_samples)},
        "vi_consumption_between": vi_consumption,
        "before": {"native_update": native_before, "oracle_update": oracle_before,
                   "native_polls": before_n.get("controller_polls"),
                   "oracle_polls": before_o.get("controller_polls"),
                   "oracle_consumed_vi": oracle_vi_before,
                   "semantic_state_match":
                       semantic_digest(before_n) == semantic_digest(before_o),
                   "actor_byte_differences": before_differences,
                   "native_rdram_sha256": n0_hash, "oracle_rdram_sha256": o0_hash},
        "after": {"native_update": native_after, "oracle_update": oracle_after,
                  "native_polls": after_n.get("controller_polls"),
                  "oracle_polls": after_o.get("controller_polls"),
                  "oracle_consumed_vi": oracle_vi_after,
                  "semantic_state_match":
                      semantic_digest(after_n) == semantic_digest(after_o),
                  "actor_byte_differences": after_differences,
                  "native_rdram_sha256": n1_hash, "oracle_rdram_sha256": o1_hash},
        "alignment_validated": False, "parity_verified": False,
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
