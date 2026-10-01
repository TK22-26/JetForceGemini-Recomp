"""Read-only exit inventory; observed connections are not proven reachable paths."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from scripts.phase95_observation import decode, physical, ObservationError


def read_exit(memory, actor, level):
    if actor.name != "exit":
        raise ObservationError("exit decoder requires an exit actor")
    base = physical(actor.address, 0x40)
    setup = physical(struct.unpack_from(">I", memory, base + 0x3C)[0], 0x1C, aligned=False)
    raw = memory[setup:setup + 0x1C]
    low, high = raw[0xA:0xC]
    destination = low if high == 255 else low | high << 8
    # No runtime heap pointer enters the semantic key. Retain the complete setup
    # digest because colocated exits can have different conditions/entry points.
    identity = {"source_level": level, "position": actor.position,
                "setup_sha256": hashlib.sha256(raw).hexdigest()}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True,
                                   separators=(",", ":")).encode()).hexdigest()
    return {**identity, "id": key, "actor": actor.address,
            "destination_level": destination,
            "world_gate": struct.unpack_from(">b", raw, 0x14)[0],
            "reachability": "unknown", "requirements": "not fully decoded"}


def inventory(memory, sequence):
    state = decode(memory, sequence=sequence)
    if state.front_mode != 16:
        raise ObservationError("world inventory requires gameplay mode")
    level = struct.unpack_from(">i", memory, 0xFB114)[0]
    exits = [read_exit(memory, actor, level) for actor in state.actors if actor.name == "exit"]
    return {"kind": "jfg-phase95-observed-world", "schema": 1, "acceptance": False,
            "level": level, "exits": exits,
            "coverage_denominator": "unknown; only currently instantiated exits observed"}


def select_exit(memory, actors, level, exit_id=None):
    candidates = [(actor, read_exit(memory, actor, level))
                  for actor in actors if actor.name == "exit"]
    if exit_id is not None:
        candidates = [(actor, item) for actor, item in candidates if item["id"] == exit_id]
    if len(candidates) != 1:
        raise ObservationError("exit identity must select exactly one current actor")
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rdram", type=Path)
    parser.add_argument("--sequence", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(inventory(args.rdram.read_bytes(), args.sequence), indent=2))


if __name__ == "__main__":
    main()
