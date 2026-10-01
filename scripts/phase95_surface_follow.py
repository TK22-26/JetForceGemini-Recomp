"""Generate and test a surface proposal from an oracle checkpoint, with bounded waypoint control."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

from scripts.phase95_bridge import Worker
from scripts.phase95_navigation import distance, navigate
from scripts.phase95_observation import decode, ObservationError
from scripts.phase95_surface_route import propose
from scripts.phase95_terrain import terrain
from scripts.phase95_world import select_exit


class Segment:
    """Disjoint checkpoint slots and diagnostic journals on one owned worker."""
    def __init__(self, worker, index):
        self.worker, self.prefix = worker, f"{index:04x}"
        self.root = worker.root / f"waypoint-{index:04d}"
        self.root.mkdir(exist_ok=False)

    def observe(self):
        return self.worker.observe()

    def act(self, action):
        return self.worker.act(action)

    def checkpoint(self, operation, slot):
        return self.worker.checkpoint(operation, self.prefix + slot)


def follow(worker, exit_id=None, actor_name=None, *, max_waypoints=256, jump=False,
           resume_proposal=None, resume_after=0, approach=None,
           short_jump=True):
    if (exit_id is None) == (actor_name is None):
        raise ValueError("select exactly one exit or actor objective")
    if actor_name is not None and actor_name != "MrHints2":
        raise ValueError("unreviewed surface actor objective")
    if approach is not None and (exit_id is None or len(approach) != 3 or
                                 not all(type(value) in (int, float) and math.isfinite(value)
                                         for value in approach)):
        raise ValueError("approach requires finite exit-route coordinates")
    if not 1 <= max_waypoints <= 256:
        raise ValueError("invalid surface waypoint budget")
    if type(resume_after) is not int or resume_after < 0 or \
            (resume_proposal is None and resume_after != 0):
        raise ValueError("completed waypoint index requires a preserved proposal")
    metadata, memory = worker.observe()
    state = decode(memory, sequence=metadata["sequence"], player_pointer=metadata["player"])
    if state.front_mode != 16 or state.player is None:
        raise ObservationError("surface following requires active player")
    level = struct.unpack_from(">i", memory, 0xFB114)[0]
    if exit_id is not None:
        target, identity = select_exit(memory, state.actors, level, exit_id)
    else:
        matches = [actor for actor in state.actors if actor.name == actor_name]
        if len(matches) != 1:
            raise ObservationError("surface actor objective must identify exactly one actor")
        target = matches[0]
        identity = {"source_level": level, "actor_name": actor_name,
                    "actor": target.address,
                    "position": target.position, "interaction_verified": False}
    if resume_proposal is None:
        proposal = propose(terrain(memory), state.player.position,
                           target.position if approach is None else approach,
                           radius=95 if approach is None else 12)
        points = list(proposal["waypoints"])
        if actor_name is not None and distance(points[-1], target.position) > 30:
            points.append(target.position)
        source = None
    else:
        raw = Path(resume_proposal).read_bytes()
        proposal = json.loads(raw)
        points = proposal.get("waypoints")
        if (proposal.get("kind") != "jfg-phase95-surface-proposal" or
                not isinstance(points, list) or not 1 < len(points) <= 257 or
                not all(isinstance(point, list) and len(point) == 3 and
                        all(type(value) in (int, float) and math.isfinite(value) for value in point)
                        for point in points) or not 0 <= resume_after <= len(points) - 1):
            raise ObservationError("invalid preserved surface route")
        prior = proposal.get("target_identity")
        if (not isinstance(prior, dict) or prior.get("source_level") != level or
                proposal.get("approach_point") != (list(approach) if approach is not None else None) or
                (actor_name is not None and
                 (prior.get("actor_name") != actor_name or prior.get("actor") != target.address)) or
                (exit_id is not None and prior.get("id") != exit_id)):
            raise ObservationError("preserved surface objective changed")
        if distance(state.player.position, points[resume_after]) > 30:
            raise ObservationError("checkpoint is not at declared route frontier")
        identity = prior
        source = {"path": str(Path(resume_proposal).resolve()),
                  "sha256": hashlib.sha256(raw).hexdigest(), "resume_after": resume_after}
    (worker.root / "surface-proposal.json").write_text(json.dumps({
        **proposal, "waypoints": points, "target_identity": identity,
        "approach_point": list(approach) if approach is not None else None,
        "jump_candidates": jump, "max_waypoints": max_waypoints,
        "source_route": source,
        **({"exit_identity": identity} if exit_id is not None else {})}, indent=2))
    selected = points[resume_after + 1:resume_after + 1 + max_waypoints]
    last_slot = f"{resume_after:04x}c1"
    dialogue_evidence = []
    for index, point in enumerate(selected, resume_after + 1):
        print(json.dumps({"waypoint": index, "target": point}), flush=True)
        segment = Segment(worker, index)
        try:
            result = navigate(segment, "surface-waypoint", waypoint=point,
                              radius=15 if approach is not None and index == len(points) - 1 else 30,
                              max_steps=8, precision=True, jump=jump,
                              short_jump=short_jump)
        except ObservationError as error:
            if actor_name != "MrHints2" or "navigation stalled" not in str(error):
                raise
            # A nearby MrHints2 conversation can temporarily lock movement.
            # Only a selected-speaker active-to-idle cycle authorizes retry.
            from scripts.phase95_dialogue import probe
            conversation = Segment(worker, index + 0x100)
            dialogue = probe(conversation, actor_name, max_steps=30)
            if not dialogue["active_then_idle"]:
                raise ObservationError("NPC dialogue did not restore route control")
            dialogue_evidence.append({"result": str((conversation.root / "dialogue-result.json")
                                                    .relative_to(worker.root)),
                                      "checkpoint": conversation.prefix + "d1"})
            segment = Segment(worker, index + 0x200)
            result = navigate(segment, "surface-waypoint", waypoint=point,
                              radius=15 if approach is not None and index == len(points) - 1 else 30,
                              max_steps=8, precision=True, jump=jump,
                              short_jump=short_jump)
        observed, raw = worker.observe()
        reached = decode(raw, sequence=observed["sequence"], player_pointer=observed["player"])
        vertical_error = abs(reached.player.position[1] - point[1])
        if vertical_error > 10:
            failure = {"kind": "jfg-phase95-surface-layer-mismatch", "acceptance": False,
                       "waypoint": index, "target": point,
                       "player_position": reached.player.position,
                       "vertical_error": vertical_error,
                       "checkpoint_slot": segment.prefix + "c1",
                       "classification": "near_waypoint_on_wrong_surface"}
            (worker.root / "surface-mismatch.json").write_text(json.dumps(failure, indent=2) + "\n")
            raise ObservationError("waypoint proximity reached on wrong surface layer")
        with (worker.root / "surface-completed.jsonl").open("a") as stream:
            stream.write(json.dumps({"waypoint": index, "result": result,
                                    "vertical_error": vertical_error,
                                    "checkpoint_slot": segment.prefix + "c1"}) + "\n")
        last_slot = segment.prefix + "c1"
    last_index = resume_after + len(selected)
    result = {"kind": "jfg-phase95-surface-follow", "acceptance": False,
              "waypoints_completed": last_index, "waypoints_in_chunk": len(selected),
              "source_route": source,
              "target_identity": identity}
    if last_index < len(points) - 1:
        result.update(completed=False,
                      frontier_checkpoint=last_slot,
                      next_waypoint=points[last_index + 1])
        (worker.root / "surface-result.json").write_text(json.dumps(result) + "\n")
        return result
    result["completed"] = True
    if exit_id is not None:
        result["exit_crossed"] = False
        result["exit_identity"] = identity
    else:
        # The surface proposal uses a fixed actor position, but MrHints2 roams.
        # Re-observe the same actor and pursue its current position in bounded
        # segments; the saved static endpoint is not an arrival predicate.
        for attempt in range(3):
            metadata, memory = worker.observe()
            final = decode(memory, sequence=metadata["sequence"],
                           player_pointer=metadata["player"])
            if (final.front_mode != 16 or final.player is None or
                    struct.unpack_from(">i", memory, 0xFB114)[0] != level):
                raise ObservationError("actor pursuit lost gameplay context")
            current = [actor for actor in final.actors if actor.name == actor_name and
                       actor.address == target.address]
            if len(current) != 1:
                raise ObservationError("declared surface actor is no longer current")
            gap = distance(final.player.position, current[0].position)
            with (worker.root / "surface-actor-pursuit.jsonl").open("a") as stream:
                stream.write(json.dumps({"attempt": attempt, "sequence": metadata["sequence"],
                                         "actor_position": current[0].position,
                                         "player_position": final.player.position,
                                         "distance": gap}) + "\n")
            if gap <= 30:
                break
            if attempt == 2:
                raise ObservationError("surface follower did not reach live actor radius")
            navigate(Segment(worker, len(points) + attempt), actor_name,
                     radius=30, max_steps=8, precision=True, jump=jump)
        result["final_actor_position"] = current[0].position
        result["actor_proximity_verified"] = gap <= 30
        result["interaction_verified"] = bool(dialogue_evidence)
        result["dialogue_evidence"] = dialogue_evidence
        if not result["actor_proximity_verified"]:
            raise ObservationError("surface follower did not reach declared actor radius")
    (worker.root / "surface-result.json").write_text(json.dumps(result) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--exit-id")
    target.add_argument("--actor-name", choices=("MrHints2",))
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--max-waypoints", type=int, default=256)
    parser.add_argument("--jump", action="store_true", help="include bounded jump candidates")
    parser.add_argument("--approach", type=float, nargs=3,
                        help="explicit reachable ground approach to a selected exit")
    parser.add_argument("--resume-proposal", type=Path,
                        help="preserve an earlier surface route instead of resampling from the new grid origin")
    parser.add_argument("--resume-after", type=int, default=0,
                        help="last completed waypoint index in the preserved route")
    args = parser.parse_args()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"), args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        follow(worker, args.exit_id, args.actor_name,
               max_waypoints=args.max_waypoints, jump=args.jump,
               resume_proposal=args.resume_proposal, resume_after=args.resume_after,
               approach=args.approach)


if __name__ == "__main__":
    main()
