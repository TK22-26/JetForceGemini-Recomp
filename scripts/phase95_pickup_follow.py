"""Follow a bounded surface route to an eligible health pickup and verify collection."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from scripts.phase95_bridge import Worker
from scripts.phase95_inventory import inventory, health_refill_collection_verified
from scripts.phase95_navigation import distance, navigate
from scripts.phase95_observation import decode, ObservationError
from scripts.phase95_surface_follow import Segment
from scripts.phase95_surface_route import propose
from scripts.phase95_terrain import terrain


def follow(worker, *, max_waypoints=32, jump=True):
    if not 1 <= max_waypoints <= 64:
        raise ValueError("invalid pickup route budget")
    metadata, memory = worker.observe()
    state = decode(memory, sequence=metadata["sequence"],
                   player_pointer=metadata["player"])
    if state.front_mode != 16 or state.player is None:
        raise ObservationError("pickup route requires active player")
    level = struct.unpack_from(">i", memory, 0xFB114)[0]
    before = inventory(memory, metadata)
    eligible = [item for item in before["health_pickups"]
                if item["name"] == "HealthPowerup" and item["eligible"]]
    if not eligible:
        raise ObservationError("no eligible ordinary health pickup observed")
    target = min(eligible, key=lambda item: distance(state.player.position,
                                                      item["position"]))
    proposal = propose(terrain(memory), state.player.position, target["position"],
                       radius=25)
    points = list(proposal["waypoints"])
    if distance(points[-1], target["position"]) > 5:
        points.append(target["position"])
    objective = {"kind": "jfg-phase95-health-pickup-objective",
                 "acceptance": False, "source_level": level,
                 "target_actor": target["actor"], "target_position": target["position"],
                 "target_kind": target["kind"], "initial_health_raw": before["health_raw"],
                 "initial_health_capacity_raw": before["health_capacity_raw"],
                 "completion": "selected actor disappears and health rises by exactly 0x100",
                 "max_waypoints": max_waypoints, "jump": jump,
                 "waypoints": points,
                 "proposal_sha256": hashlib.sha256(json.dumps(proposal, sort_keys=True)
                                                   .encode()).hexdigest()}
    (worker.root / "pickup-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    completed = 0
    for index, point in enumerate(points[1:max_waypoints + 1], 1):
        print(json.dumps({"pickup_waypoint": index, "target": point}), flush=True)
        segment = Segment(worker, index)
        error = None
        try:
            navigate(segment, "surface-waypoint", waypoint=point,
                     radius=5 if index == len(points) - 1 else 30,
                     max_steps=8, precision=True, jump=jump)
        except ObservationError as caught:
            if str(caught) not in ("navigation stalled; global routing or another action is needed",
                                   "navigation step budget exhausted"):
                raise
            error = caught
        metadata, memory = worker.observe()
        if struct.unpack_from(">i", memory, 0xFB114)[0] != level:
            raise ObservationError("pickup route crossed an unplanned level transition")
        current = decode(memory, sequence=metadata["sequence"],
                         player_pointer=metadata["player"])
        after = inventory(memory, metadata)
        collected = health_refill_collection_verified(before, after, target)
        vertical_error = abs(current.player.position[1] - point[1])
        if not collected and error is None and vertical_error > 10:
            raise ObservationError("pickup waypoint reached on wrong surface layer")
        with (worker.root / "pickup-progress.jsonl").open("a") as stream:
            stream.write(json.dumps({"waypoint": index, "checkpoint": segment.prefix + "c1"
                                     if error is None else None,
                                     "health_before": before["health_raw"],
                                     "health_after": after["health_raw"],
                                     "vertical_error": vertical_error,
                                     "target_present": any(item["actor"] == target["actor"]
                                                           for item in after["health_pickups"]),
                                     "collection_verified": collected,
                                     "navigation_error": str(error) if error else None}) + "\n")
        if collected:
            worker.checkpoint("save", "e1")
            worker.observe()
            result = {**objective, "completed": True, "waypoints_completed": index,
                      "final_health_raw": after["health_raw"],
                      "final_sequence": metadata["sequence"], "checkpoint": "e1"}
            (worker.root / "pickup-result.json").write_text(json.dumps(result, indent=2) + "\n")
            return result
        if not any(item["actor"] == target["actor"] for item in after["health_pickups"]):
            raise ObservationError("selected health pickup vanished without exact collection effect")
        if error is not None:
            raise error
        before = after
        completed = index
    result = {**objective, "completed": False, "waypoints_completed": completed,
              "classification": ("route_budget_exhausted" if completed < len(points) - 1
                                 else "pickup_not_collected")}
    (worker.root / "pickup-result.json").write_text(json.dumps(result, indent=2) + "\n")
    raise ObservationError("health pickup not verified within route budget")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--max-waypoints", type=int, default=32)
    parser.add_argument("--no-jump", action="store_true")
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    args = parser.parse_args()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        follow(worker, max_waypoints=args.max_waypoints, jump=not args.no_jump)


if __name__ == "__main__":
    main()
