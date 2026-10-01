"""Finish the Goldwood east/level-48 branch from a sealed ground-route frontier."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

from scripts.phase95_bridge import Worker
from scripts.phase95_exit import cross
from scripts.phase95_navigation import navigate, distance
from scripts.phase95_observation import decode, ObservationError
from scripts.phase95_surface_follow import Segment
from scripts.phase95_surface_route import propose
from scripts.phase95_terrain import terrain
from scripts.phase95_world import select_exit


EAST_EXIT_48 = "24196c48658bcfd621800edc11d4a90b207328c670d089c2f3fecd809ae8347a"
APPROACH = (730.0, 14.0, -305.0)


def finish(worker, *, route_template=None):
    metadata, memory = worker.observe()
    state = decode(memory, sequence=metadata["sequence"], player_pointer=metadata["player"])
    if state.front_mode != 16 or state.player is None or \
            struct.unpack_from(">i", memory, 0xFB114)[0] != 47:
        raise ObservationError("east branch requires level-47 player context")
    actor, identity = select_exit(memory, state.actors, 47, EAST_EXIT_48)
    if route_template is None:
        proposal = propose(terrain(memory), state.player.position, APPROACH, radius=12)
        points = proposal["waypoints"][1:]
        template = None
    else:
        route_template = Path(route_template).resolve()
        raw = route_template.read_bytes()
        reviewed = json.loads(raw)
        if (reviewed.get("kind") != "jfg-phase95-east-branch-finish" or
                not reviewed.get("completed") or
                reviewed.get("exit_identity", {}).get("id") != EAST_EXIT_48 or
                reviewed.get("destination_level") != 48 or
                reviewed.get("approach") != list(APPROACH)):
            raise ObservationError("east ground route template identity mismatch")
        points = reviewed.get("waypoints")
        template = {"path": str(route_template),
                    "sha256": hashlib.sha256(raw).hexdigest()}
        if (not isinstance(points, list) or not 1 <= len(points) <= 8 or
                not all(isinstance(point, list) and len(point) == 3 and
                        all(type(value) in (int, float) and math.isfinite(value)
                            for value in point) for point in points)):
            raise ObservationError("east ground route template has invalid waypoints")
        if distance(state.player.position, points[0]) > 80:
            raise ObservationError("east ground route starts beyond reviewed frontier")
    if not 1 <= len(points) <= 8:
        raise ObservationError("east exit ground approach exceeds waypoint budget")
    objective = {"kind": "jfg-phase95-east-branch-finish", "acceptance": False,
                 "source_level": 47, "destination_level": 48,
                 "exit_identity": identity, "approach": APPROACH,
                 "waypoints": points, "route_template": template,
                 "completion": "three stable level-48 playerBoy samples"}
    (worker.root / "branch-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    for index, point in enumerate(points, 1):
        segment = Segment(worker, index)
        result = navigate(segment, "surface-waypoint", waypoint=point,
                          radius=20, max_steps=8, precision=True, jump=False)
        metadata, memory = worker.observe()
        current = decode(memory, sequence=metadata["sequence"],
                         player_pointer=metadata["player"])
        vertical_error = abs(current.player.position[1] - point[1])
        if vertical_error > 10:
            raise ObservationError("east branch approach crossed wrong surface layer")
        with (worker.root / "branch-waypoints.jsonl").open("a") as stream:
            stream.write(json.dumps({"index": index, "point": point,
                                     "vertical_error": vertical_error,
                                     "result": result}) + "\n")
        print(json.dumps({"east_waypoint": index, "position": current.player.position}), flush=True)
    gap = distance(current.player.position, actor.position)
    if gap > 100:
        raise ObservationError(f"east exit remains outside crossing radius: {gap:.2f}")
    crossing = Segment(worker, 0x20)
    result = cross(crossing, exit_id=EAST_EXIT_48)
    if not result["completed"] or result["destination_level"] != 48:
        raise ObservationError("east exit crossing not verified")
    metadata, memory = worker.observe()
    summary = {**objective, "completed": True, "exit_gap_before_crossing": gap,
               "waypoints_completed": len(points),
               "crossing": result,
               "final_frame": metadata["frame"], "final_polls": metadata["polls"],
               "final_rdram_sha256": hashlib.sha256(memory).hexdigest()}
    (worker.root / "branch-result.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--route-template", type=Path,
                        help="reviewed ordinary-input ground waypoints from a successful finish")
    args = parser.parse_args()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        finish(worker, route_template=args.route_template)


if __name__ == "__main__":
    main()
