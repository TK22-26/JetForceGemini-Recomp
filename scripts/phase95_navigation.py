"""Checkpoint lookahead navigation to an observed landmark; ordinary inputs only.

This local planner does not claim global pathfinding or hidden-branch coverage.
Every trial and rollback remains in the worker journal; selected actions are
also recorded separately so exploration trials are not mistaken for one replay.
"""
from dataclasses import asdict
import hashlib
import json
import math
import struct

from scripts.phase95_bridge import Action
from scripts.phase95_observation import ObservationError, decode
from scripts.phase95_world import inventory, select_exit


def distance(position, target):
    if len(position) != 3 or len(target) != 3 or not all(
            math.isfinite(v) for v in (*position, *target)):
        raise ValueError("invalid navigation position")
    return math.dist(position, target)


def jump_mask(memory):
    """Read the jump action at controlModeKeys +0x0C, pinned to both US tables."""
    if struct.unpack_from(">9I", memory, 0xA18B4) != (
            0x2000, 0x8, 0x4, 0x8000, 0x4000, 0x2, 0x1, 0x8000, 0x4000):
        raise ObservationError("normal control mapping profile mismatch")
    if struct.unpack_from(">9I", memory, 0xA18D8) != (
            0x2000, 0x4000, 0x8000, 0x8, 0x4, 0x2, 0x1, 0x8, 0x4):
        raise ObservationError("expert control mapping profile mismatch")
    selected = struct.unpack_from(">I", memory, 0xA18B0)[0]
    if selected == 0x800A18B4:
        return 0x8000
    if selected == 0x800A18D8:
        return 0x0008
    raise ObservationError("unknown active control mapping")


def navigation_candidates(jump=False, precision=False, jump_button=None,
                          short_jump=True):
    directions = ((0, 60), (-60, 60), (60, 60), (-60, 0), (60, 0),
                  (0, -60), (-60, -60), (60, -60))
    candidates = [(Action(24, x=x, y=y),) for x, y in directions]
    if precision:
        candidates.extend((Action(frames, x=x, y=y),)
                          for frames in (6, 12) for x, y in directions)
        candidates.append((Action(24),))
    if jump:
        if jump_button not in (0x8000, 0x0008):
            raise ValueError("jump candidates require a validated control button")
        # Release the configured jump button before each edge; observe each action.
        candidates.extend((Action(6), Action(24, buttons=jump_button, x=x, y=y),
                           Action(48, x=x, y=y)) for x, y in directions)
        # Nearby ledges need a short airborne steering pulse followed by release;
        # the long option above can overshoot by hundreds of world units.
        if short_jump:
            candidates.extend((Action(6), Action(12, buttons=jump_button, x=x, y=y),
                               Action(48)) for x, y in directions)
    return candidates


def navigate(worker, target_name, *, max_steps=40, radius=65.0, exit_id=None,
             jump=False, jump_button=None, waypoint=None, precision=False,
             short_jump=True):
    if target_name not in ("longwoodbridge", "MrHints2", "exit", "surface-waypoint"):
        raise ValueError("unreviewed navigation objective")
    if (waypoint is not None) != (target_name == "surface-waypoint"):
        raise ValueError("surface waypoint requires explicit coordinates")
    if waypoint is not None:
        distance(waypoint, waypoint)
    if not 1 <= max_steps <= 100 or not 1 <= radius <= 100:
        raise ValueError("invalid navigation budget")
    if exit_id is not None and target_name != "exit":
        raise ValueError("exit identity requires exit objective")

    def observe():
        metadata, memory = worker.observe()
        state = decode(memory, sequence=metadata["sequence"],
                       player_pointer=metadata["player"] or None)
        if state.front_mode != 16 or state.player is None:
            raise ObservationError("navigation lost active player")
        return metadata, memory, state

    metadata, memory, state = observe()
    if jump:
        resolved_jump_button = jump_mask(memory) if jump_button is None else jump_button
        if resolved_jump_button not in (0x8000, 0x0008):
            raise ValueError("invalid jump button override")
    else:
        resolved_jump_button = None
    matches = [actor for actor in state.actors if actor.name == target_name]
    level = struct.unpack_from(">i", memory, 0xFB114)[0]
    selected_exit = None
    if target_name == "exit":
        actor, selected_exit = select_exit(memory, state.actors, level, exit_id)
        matches = [actor]
        (worker.root / "world-inventory.json").write_text(json.dumps(
            inventory(memory, metadata["sequence"]), indent=2))
    if waypoint is None and len(matches) != 1:
        raise ObservationError("objective must identify exactly one landmark")
    target = tuple(waypoint) if waypoint is not None else matches[0].position
    tracked_actor = matches[0].address if target_name == "MrHints2" else None

    def current_target(observation):
        if tracked_actor is None:
            return target
        current = [actor for actor in observation.actors
                   if actor.name == target_name and actor.address == tracked_actor]
        if len(current) != 1:
            raise ObservationError("tracked navigation actor is no longer current")
        return current[0].position

    objective = {"kind": "jfg-phase95-landmark-objective", "acceptance": False,
                 "target_name": target_name, "target_position": target,
                 "tracked_actor": tracked_actor,
                 "radius": radius, "max_steps": max_steps, "level_number": level,
                 "initial_sequence": metadata["sequence"], "jump_candidates": jump,
                 "short_jump_candidates": short_jump,
                 "jump_button": resolved_jump_button,
                 "precision_candidates": precision,
                 "completion": ("player within 3D radius of live tracked actor"
                                if tracked_actor is not None else
                                "player within 3D radius of fixed observed landmark")}
    if selected_exit is not None:
        objective["exit_identity"] = selected_exit
    (worker.root / "navigation-objective.json").write_text(json.dumps(objective, indent=2))
    candidates = navigation_candidates(jump, precision, resolved_jump_button,
                                       short_jump=short_jump)

    def execute(actions):
        trajectory = []
        for action in actions:
            worker.act(action)
            result = observe()
            if struct.unpack_from(">i", result[1], 0xFB114)[0] != level:
                raise ObservationError("lookahead crossed an unplanned level transition")
            trajectory.append({"frame": result[0].get("frame"),
                               "polls": result[0].get("polls"),
                               "player": result[0]["player"],
                               "position": result[2].player.position,
                               "sha256": hashlib.sha256(result[1]).hexdigest()})
        return (*result, trajectory)
    stalled = 0
    for step in range(max_steps + 1):
        before = distance(state.player.position, current_target(state))
        if before <= radius:
            worker.checkpoint("save", "c1")
            metadata, memory, state = observe()
            result = {**objective, "completed": True, "steps": step,
                      "distance": before, "final_sequence": metadata["sequence"]}
            (worker.root / "navigation-result.json").write_text(json.dumps(result, indent=2))
            return result
        if step == max_steps:
            break
        slot = f"b{step:04x}"
        worker.checkpoint("save", slot)
        observe()
        trials = []
        for index, actions in enumerate(candidates):
            worker.checkpoint("load", slot)
            observe()
            trial_metadata, trial_memory, trial_state, trajectory = execute(actions)
            trial = {"step": step, "candidate": index,
                     "actions": [asdict(action) for action in actions],
                     "trajectory": trajectory,
                     "distance": distance(trial_state.player.position,
                                          current_target(trial_state)),
                     "sequence": trial_metadata["sequence"],
                     "sha256": hashlib.sha256(trial_memory).hexdigest()}
            if len(actions) == 1:
                trial["action"] = asdict(actions[0])
            trials.append(trial)
            with (worker.root / "navigation-trials.jsonl").open("a") as stream:
                stream.write(json.dumps(trial) + "\n")
        best = min(trials, key=lambda item: (item["distance"], item["candidate"]))
        worker.checkpoint("load", slot)
        observe()
        metadata, memory, state, trajectory = execute(candidates[best["candidate"]])
        if trajectory != best["trajectory"] or hashlib.sha256(memory).hexdigest() != best["sha256"]:
            raise ObservationError("selected lookahead failed exact continuation check")
        selected = {**best, "execution_sequence": metadata["sequence"], "checkpoint": slot}
        with (worker.root / "navigation-selected.jsonl").open("a") as stream:
            stream.write(json.dumps(selected) + "\n")
        print(json.dumps({"navigation_step": step, "distance": best["distance"]}), flush=True)
        stalled = stalled + 1 if best["distance"] >= before - 1 else 0
        if stalled >= 5:
            raise ObservationError("navigation stalled; global routing or another action is needed")
    raise ObservationError("navigation step budget exhausted")
