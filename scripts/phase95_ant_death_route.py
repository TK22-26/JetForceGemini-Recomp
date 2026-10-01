"""Approach an observed level-21 BlueAnt and probe natural damage/death."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from scripts.phase95_bridge import Worker
from scripts.phase95_death_probe import probe as death_probe
from scripts.phase95_navigation import distance, navigate
from scripts.phase95_observation import decode, ObservationError
from scripts.phase95_surface_follow import Segment
from scripts.phase95_surface_route import propose
from scripts.phase95_terrain import terrain


def approach(worker, *, max_waypoints=50):
    metadata, memory = worker.observe()
    state = decode(memory, sequence=metadata["sequence"],
                   player_pointer=metadata["player"])
    if state.front_mode != 16 or state.player is None or \
            struct.unpack_from(">i", memory, 0xFB114)[0] != 21:
        raise ObservationError("ant death route requires level-21 player")
    ants = [actor for actor in state.actors if actor.name == "BlueAnt"]
    if not ants:
        raise ObservationError("no live BlueAnt observed at death-route frontier")
    target = min(ants, key=lambda actor: distance(state.player.position, actor.position))
    plan = propose(terrain(memory), state.player.position, target.position, radius=45)
    points = plan["waypoints"][1:]
    if not 1 <= len(points) <= max_waypoints:
        raise ObservationError("ant route outside declared waypoint budget")
    objective = {"kind": "jfg-phase95-ant-approach", "acceptance": False,
                 "source_level": 21, "target_actor": target.address,
                 "target_initial_position": target.position,
                 "waypoints": points, "max_waypoints": max_waypoints,
                 "completion": "observed route frontier with at least one live BlueAnt; actor proximity and damage source are not inferred"}
    (worker.root / "ant-approach-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    for index, point in enumerate(points, 1):
        segment = Segment(worker, index)
        result = navigate(segment, "surface-waypoint", waypoint=point,
                          radius=30, max_steps=8, precision=True, jump=False)
        metadata, memory = worker.observe()
        state = decode(memory, sequence=metadata["sequence"],
                       player_pointer=metadata["player"])
        if state.front_mode != 16 or state.player is None or \
                struct.unpack_from(">i", memory, 0xFB114)[0] != 21:
            raise ObservationError("ant approach lost level-21 player")
        error = abs(state.player.position[1] - point[1])
        if error > 10:
            raise ObservationError("ant approach crossed wrong vertical layer")
        with (worker.root / "ant-route-waypoints.jsonl").open("a") as stream:
            stream.write(json.dumps({"index": index, "target": point,
                                     "vertical_error": error,
                                     "result": result}) + "\n")
        print(json.dumps({"ant_waypoint": index, "distance": result["distance"]}), flush=True)
    current = [actor for actor in state.actors if actor.address == target.address and
               actor.name == "BlueAnt"]
    gap = distance(state.player.position, current[0].position) if len(current) == 1 else None
    live_ants = [actor for actor in state.actors if actor.name == "BlueAnt"]
    if not live_ants:
        raise ObservationError("ant approach lost all observed live BlueAnt actors")
    worker.checkpoint("save", "a1")
    frontier_metadata, frontier_memory = worker.observe()
    summary = {**objective, "completed": True, "target_gap": gap,
               "target_proximity_verified": gap is not None and gap <= 80,
               "live_ant_count": len(live_ants),
               "route_waypoints": len(points), "frontier_checkpoint": "a1",
               "frontier_frame": frontier_metadata["frame"],
               "frontier_rdram_sha256": hashlib.sha256(frontier_memory).hexdigest()}
    (worker.root / "ant-approach-result.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def run(worker, *, max_waypoints=50, death_steps=120):
    approach_result = approach(worker, max_waypoints=max_waypoints)
    objective = {"kind": "jfg-phase95-ant-death-route", "acceptance": False,
                 "approach_checkpoint": approach_result["frontier_checkpoint"],
                 "approach_rdram_sha256": approach_result["frontier_rdram_sha256"],
                 "death_steps": death_steps,
                 "completion": "live ant approach followed by observed natural health depletion"}
    (worker.root / "ant-death-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    result = death_probe(worker, max_steps=death_steps, unchanged_budget=30)
    summary = {**objective, "approach": approach_result,
               "completed": result.get("health_depleted_observed", False),
               "death_probe": result,
               "final_rdram_sha256": hashlib.sha256(worker.observe()[1]).hexdigest()}
    (worker.root / "ant-death-result.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--max-waypoints", type=int, default=50)
    parser.add_argument("--death-steps", type=int, default=120)
    args = parser.parse_args()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        run(worker, max_waypoints=args.max_waypoints,
            death_steps=args.death_steps)


if __name__ == "__main__":
    main()
