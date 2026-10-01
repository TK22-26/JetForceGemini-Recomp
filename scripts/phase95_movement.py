"""Bounded live movement measurement, not a navigation/encounter acceptance test."""
from dataclasses import asdict
import argparse
from pathlib import Path
import json
import hashlib
import math
import struct

from scripts.phase95_bridge import Action, Worker
from scripts.phase95_observation import ObservationError, decode


def displacement(before, after):
    if len(before) != 3 or len(after) != 3 or not all(
            math.isfinite(value) for value in (*before, *after)):
        raise ValueError("invalid movement coordinates")
    delta = tuple(b - a for a, b in zip(before, after))
    return {"delta": delta, "horizontal": math.hypot(delta[0], delta[2])}


def measure(worker, verify_checkpoint=False):
    metadata, memory = worker.observe()
    initial = decode(memory, sequence=metadata["sequence"],
                     player_pointer=metadata["player"])
    if initial.front_mode != 16 or initial.player is None:
        raise ObservationError("movement probe requires active player mode")
    level = struct.unpack_from(">i", memory, 0xFB114)[0]
    previous = initial.player
    records = []
    continuation = []
    # Let the entry animation settle, then test small controlled inputs.
    probes = [("settle", Action(120))] * 5 + [
        ("forward", Action(60, y=60)), ("release", Action(30)),
        ("turn-right", Action(30, x=60)), ("release", Action(30)),
        ("forward-after-turn", Action(60, y=60)), ("release", Action(30)),
    ]
    for name, action in probes:
        if verify_checkpoint and name == "forward":
            worker.checkpoint("save", "a1")
            worker.observe()
        worker.act(action)
        metadata, memory = worker.observe()
        observation = decode(memory, sequence=metadata["sequence"],
                             player_pointer=metadata["player"])
        if observation.front_mode != 16 or struct.unpack_from(">i", memory, 0xFB114)[0] != level:
            raise ObservationError("movement probe crossed an unplanned transition")
        current = observation.player
        record = {"probe": name, "action": asdict(action), **metadata,
                  "before": asdict(previous), "after": asdict(current),
                  **displacement(previous.position, current.position),
                  "yaw_delta": ((current.yaw - previous.yaw + 32768) % 65536) - 32768}
        with (worker.root / "movement.jsonl").open("a") as stream:
            stream.write(json.dumps(record, allow_nan=False) + "\n")
        print(json.dumps(record), flush=True)
        records.append(record)
        if name != "settle":
            continuation.append((action, metadata, memory))
        previous = current
    result = {"kind": "jfg-phase95-movement-probe", "acceptance": False,
              "level_number": level,
              "forward_response": next(r["horizontal"] for r in records if r["probe"] == "forward"),
              "turn_response": next(r["yaw_delta"] for r in records if r["probe"] == "turn-right")}
    if verify_checkpoint:
        worker.checkpoint("load", "a1")
        worker.observe()
        checks = []
        for index, (action, expected_metadata, expected_memory) in enumerate(continuation):
            worker.act(action)
            actual_metadata, actual_memory = worker.observe()
            equal = actual_memory == expected_memory and all(
                actual_metadata[key] == expected_metadata[key]
                for key in ("frame", "polls", "player"))
            check = {"step": index, "equal": equal,
                     "expected_sha256": hashlib.sha256(expected_memory).hexdigest(),
                     "actual_sha256": hashlib.sha256(actual_memory).hexdigest(),
                     "expected": expected_metadata, "actual": actual_metadata}
            checks.append(check)
            with (worker.root / "gameplay-restore.jsonl").open("a") as stream:
                stream.write(json.dumps(check) + "\n")
            if not equal:
                (worker.root / "restore-expected.rdram").write_bytes(expected_memory)
                (worker.root / "restore-actual.rdram").write_bytes(actual_memory)
                raise ObservationError(f"gameplay restore differs at continuation step {index}")
        result["checkpoint_continuation_equal"] = all(check["equal"] for check in checks)
        result["checkpoint_steps"] = len(checks)
    (worker.root / "movement-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    args = parser.parse_args()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        measure(worker, verify_checkpoint=True)


if __name__ == "__main__":
    main()
