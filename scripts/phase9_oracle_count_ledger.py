"""Reconcile oracle CPU mutations with independently recorded device events.

This establishes a local Count ledger, not a retirement clock, cross-engine
alignment, capture non-perturbation, or a causal repair. Count writes/resets
remain explicit mutations; ERET's nested lazy update is never paid twice.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from scripts import phase9_device_events as devices
from scripts import phase9_oracle_cpu_boundaries as boundaries
from scripts.phase95_bridge import digest

MASK = 0xffffffff
LIMITS = {"clock_alignment_validated": False, "retirement_validated": False,
          "causal_fix_proved": False, "parity_verified": False,
          "game_nonperturbation_qualified": False}


def project_observations(observations):
    """Bounded planner view; full per-PC counts and ERET contexts stay pinned."""
    keys = ("first_device_sequence_inclusive", "last_device_sequence_exclusive", "start", "end",
            "cpu_events", "count_events", "eret_events", "mutations_by_reason", "net_count_change_u32",
            "contains_count_write_or_reset", "elapsed_or_retired_ticks_proved")
    return [{"update": row["update"], "device_events_reconciled": row["device_events_reconciled"],
             "oracle_count_ledger": {key: row["oracle_count_ledger"][key] for key in keys},
             "clock_alignment_validated": False, "retirement_validated": False,
             "causal_fix_proved": False} for row in observations]


def reconcile(cpu_rows, device_rows, update):
    """Join already schema-validated streams using producer event sequence.

    device_sequence=d means a CPU row was emitted AFTER device row d and
    BEFORE device row d+1. Equal Count values never choose or shift a join.
    """
    if type(update) is not int or not 1 <= update <= 1000000 or not cpu_rows or not device_rows:
        raise ValueError("Count ledger requires a nonempty bounded invocation")
    if (len(cpu_rows) > boundaries.MAX_ROWS or len(device_rows) > devices.MAX_ROWS or
            any(row["sequence"] != i for i, row in enumerate(device_rows, 1)) or
            any(row["sequence"] != i or row["invocation"] != update
                for i, row in enumerate(cpu_rows, 1))):
        raise ValueError("Count ledger input ordering or budget differs")
    selected = [row for row in device_rows if row["invocation"] == update]
    if not selected:
        raise ValueError("Count ledger invocation has no device witnesses")
    first, last = selected[0]["sequence"], selected[-1]["sequence"]
    previous = first - 1
    for row in cpu_rows:
        if not previous <= row["device_sequence"] <= last:
            raise ValueError("CPU mutation escaped its device invocation or reversed its join")
        previous = row["device_sequence"]
    if cpu_rows[0]["kind"] != "count":
        raise ValueError("Count ledger has no initial mutation state")
    count, cursor, joined = cpu_rows[0]["count_before"], 0, []

    def apply(row):
        nonlocal count
        if row["kind"] == "count":
            if row["count_before"] != count:
                raise ValueError("Count ledger has an unaccounted mutation")
            count = row["count_after"]
        elif row["kind"] != "eret" or row["count_after"] != count:
            raise ValueError("ERET disagrees with its already-paid Count update")

    for device in selected:
        start = cursor
        while cursor < len(cpu_rows) and cpu_rows[cursor]["device_sequence"] < device["sequence"]:
            apply(cpu_rows[cursor])
            cursor += 1
        if count != device["clock_raw"]:
            raise ValueError(f"Count/device contradiction at device sequence {device['sequence']}")
        consumed = cpu_rows[start:cursor]
        joined.append({"device_sequence": device["sequence"], "phase": device["phase"],
            "source": device["source"], "pc": device["pc"], "count": count,
            "cpu_first_sequence": start + 1 if consumed else None,
            "cpu_last_sequence": cursor if consumed else None,
            "count_rows": sum(row["kind"] == "count" for row in consumed),
            "eret_rows": sum(row["kind"] == "eret" for row in consumed)})
    # The completed CPU footer can include mutations after the final device
    # witness. Keep them separate; no device agreement is asserted for them.
    unwitnessed = len(cpu_rows) - cursor
    for row in cpu_rows[cursor:]:
        apply(row)
    return {"update": update, "joined_devices": joined,
            "cpu_events_after_last_device": unwitnessed,
            "final_logged_count": count, "device_count_consistency_verified": True,
            **LIMITS}


def interval(cpu_rows, device_rows, joined, first, last):
    """Summarize a fixed instruction-entry interval; never discover an alignment."""
    if (type(first) is not int or type(last) is not int or
            not 1 <= first < last <= len(device_rows)):
        raise ValueError("Count interval needs two ordered device sequences")
    start, end = device_rows[first - 1], device_rows[last - 1]
    if (any(row["phase"] != "instruction" or row["invocation"] != joined["update"]
            for row in (start, end)) or
            not {first, last} <= {row["device_sequence"] for row in joined["joined_devices"]}):
        raise ValueError("Count interval boundaries are not witnessed instruction entries")
    selected = [row for row in cpu_rows if first <= row["device_sequence"] < last]
    paid, eret = [row for row in selected if row["kind"] == "count"], [row for row in selected if row["kind"] == "eret"]
    count = start["clock_raw"]
    totals = {}
    for row in paid:
        if row["count_before"] != count:
            raise ValueError("Count interval omits a mutation at its start or middle")
        count = row["count_after"]
        reason = row["reason"]
        total = totals.setdefault(reason, {"events": 0, "modular_delta": 0})
        total["events"] += 1
        total["modular_delta"] = (total["modular_delta"] + row["count_after"] - row["count_before"]) & MASK
    if count != end["clock_raw"]:
        raise ValueError("Count interval omits a mutation before its end")
    boundary_keys = ("sequence", "invocation", "pc", "opcode", "clock_raw", "clock_anchor_pc", "status", "cause", "thread")
    eret_keys = ("sequence", "device_sequence", "pc", "target_pc", "count_before", "count_after",
                 "anchor_before", "anchor_after", "status_before", "status_after",
                 "thread_word_before", "thread_word_after", "previous_eret_thread_word")
    return {"first_device_sequence_inclusive": first, "last_device_sequence_exclusive": last,
            "start": {key: start[key] for key in boundary_keys},
            "end": {key: end[key] for key in boundary_keys},
            "cpu_events": len(selected), "count_events": len(paid), "eret_events": len(eret),
            "net_count_change_u32": (end["clock_raw"] - start["clock_raw"]) & MASK,
            "mutations_by_reason": dict(sorted(totals.items())),
            "contains_count_write_or_reset": any(reason in totals for reason in ("write", "nmi-reset", "hard-reset")),
            "eret_boundaries": [{key: row[key] for key in eret_keys} for row in eret],
            "pc_mutation_counts": [{"pc": pc, "events": count} for pc, count in
                sorted(Counter(row["pc"] for row in paid).items())],
            "elapsed_or_retired_ticks_proved": False}


def measure(directory, *, first, last):
    directory = Path(directory).resolve(strict=True)
    paths = [directory / name for name in ("oracle-result.json", "cpu-boundaries.tsv", "device-events.tsv")]
    before = {str(path): digest(path) for path in paths}
    metadata = json.loads(paths[0].read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("Count ledger capture metadata is not an object")
    cpu_spec, device_spec = metadata.get("cpu_boundaries"), metadata.get("device_events")
    if (type(metadata.get("exit_code")) is not int or metadata["exit_code"] != 0 or metadata.get("trace_complete") is not True or
            metadata.get("completed_update_trace_complete") is not True or
            metadata.get("focused_update_capture_complete") is not True or
            metadata.get("preferred_n64_core_override") is not None or
            not isinstance(cpu_spec, dict) or not isinstance(device_spec, dict)):
        raise ValueError("Count ledger capture is incomplete or lacks explicit observations")
    focus, window, pcs = metadata.get("focused_update_range"), device_spec.get("window"), device_spec.get("pcs")
    if (any(not isinstance(pair, list) or len(pair) != 2 or
            any(type(value) is not int for value in pair) or not 1 <= pair[0] <= pair[1] <= 1000000
            for pair in (focus, window)) or not isinstance(pcs, list) or not 1 <= len(pcs) <= 16 or
            any(type(pc) is not int or not 0x80000000 <= pc <= 0x803ffffc or pc % 4 for pc in pcs) or
            len(set(pcs)) != len(pcs)):
        raise ValueError("Count ledger capture window or instruction points are malformed")
    update = cpu_spec.get("update")
    specification = boundaries.specification(update, device_spec, metadata.get("mupen_cpu_core_override"))
    if specification is None or any(cpu_spec.get(key) != value for key, value in specification.items()):
        raise ValueError("Count ledger CPU declaration differs")
    expected_device = devices.specification(True, device_spec.get("pcs"), metadata.get("focused_update_range"),
                                            side="oracle", qualified_engine=True)
    if any(device_spec.get(key) != value for key, value in expected_device.items()):
        raise ValueError("Count ledger device declaration differs")
    for path, spec, summary in ((paths[1], cpu_spec, boundaries.summary(paths[1], cpu_spec)),
            (paths[2], device_spec, devices.summary(paths[2], device_spec, side="oracle"))):
        if (summary.get("complete") is not True or spec.get("sha256") != before[str(path)] or
                any(spec.get(key) != value for key, value in summary.items())):
            raise ValueError("Count ledger trace summary, footer or digest differs")
    cpu = boundaries.read(paths[1], update)["rows"]
    device = devices.read(paths[2], device_spec["window"], side="oracle")["rows"]
    joined = reconcile(cpu, device, update)
    selected = interval(cpu, device, joined, first, last)
    if before != {str(path): digest(path) for path in paths}:
        raise ValueError("Count ledger evidence changed during measurement")
    return {"kind": "jfg-oracle-count-ledger", "schema": 1, "complete": True,
            "evidence": before, "ledger": joined, "interval": selected, **LIMITS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--first-device-sequence", type=int, required=True)
    parser.add_argument("--last-device-sequence", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Exclusive creation preserves every earlier artifact, including failures.
    if args.output.exists():
        raise FileExistsError(args.output)
    report = measure(args.directory, first=args.first_device_sequence, last=args.last_device_sequence)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"output": str(args.output), "sha256": digest(args.output),
                      "device_events_reconciled": len(report["ledger"]["joined_devices"]),
                      "interval_count_events": report["interval"]["count_events"],
                      "causal_fix_proved": False}))


if __name__ == "__main__":
    main()
