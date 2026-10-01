"""Bounded ordinary-input exit crossing from a sealed nearby oracle frontier."""
import argparse
import json
from pathlib import Path
import struct

from scripts.phase95_bridge import Action, Worker
from scripts.phase95_navigation import distance
from scripts.phase95_observation import decode, ObservationError, FRONT_MODE
from scripts.phase95_world import select_exit


REGION_PROMPT = 0xA329C
REQUESTED_LEVEL = 0xA3250
PAUSE_MODE = 0xFD7BD


def load_search_source(search_result_path, checkpoint_path, exit_id):
    """Bind an in-flight exit objective to a replay-equal nearby checkpoint."""
    if search_result_path.parent.resolve() != checkpoint_path.parent.resolve():
        raise ValueError("search result must belong to checkpoint worker")
    result = json.loads(search_result_path.read_text())
    checkpoint = json.loads(checkpoint_path.read_text())
    identity = result.get("exit_identity")
    if result.get("kind") != "jfg-phase95-checkpoint-search" or \
            result.get("completed") is not True or result.get("replay_equal") is not True or \
            result.get("final_rdram_sha256") != checkpoint.get("rdram_sha256") or \
            checkpoint.get("kind") != "jfg-phase95-checkpoint" or \
            not isinstance(identity, dict) or identity.get("id") != exit_id:
        raise ValueError("search result does not seal this exit checkpoint")
    return identity


def exit_objective(memory, metadata, exit_id=None, source_identity=None):
    state = decode(memory, sequence=metadata["sequence"], player_pointer=metadata["player"])
    if state.front_mode != 16 or state.player is None:
        raise ObservationError("exit probe requires an active player")
    level = struct.unpack_from(">i", memory, 0xFB114)[0]
    try:
        actor, identity = select_exit(memory, state.actors, level, exit_id)
        position = actor.position
        present = True
    except ObservationError:
        if source_identity is None or exit_id is None or \
                source_identity.get("id") != exit_id or \
                source_identity.get("source_level") != level:
            raise
        # A nearby exit actor may already have been removed by its trigger.
        # This fallback is allowed only when it is absent, not ambiguous.
        from scripts.phase95_world import read_exit
        if any(read_exit(memory, candidate, level)["id"] == exit_id
               for candidate in state.actors if candidate.name == "exit"):
            raise ObservationError("selected exit is still present but ambiguous")
        identity = source_identity
        position = identity["position"]
        present = False
    destination = identity["destination_level"]
    # Nonnegative world gates can redirect to character/world selection.
    if identity["world_gate"] != -1:
        raise ObservationError("world-gated exit requires a separate objective")
    if destination == level or distance(state.player.position, position) > 100:
        raise ObservationError("exit probe requires a nearby different-level exit")
    return {"kind": "jfg-phase95-exit-objective", "acceptance": False,
            "source_level": level, "destination_level": destination,
            "exit_actor": identity["actor"], "exit_position": position,
            "exit_identity": identity,
            "exit_actor_present": present,
            "completion": "three observations of playerBoy in mode 16 at declared destination"}


class Arrival:
    def __init__(self, destination):
        self.destination = destination
        self.samples = 0

    def accept(self, mode, level, player_name):
        self.samples = self.samples + 1 if (
            mode == 16 and level == self.destination and player_name == "playerBoy") else 0
        return self.samples >= 3


def cross(worker, action=Action(60, y=60), max_steps=100, exit_id=None,
          arrival_level=None, source_identity=None):
    action.validate()
    if not 1 <= max_steps <= 100:
        raise ValueError("invalid exit budget")
    metadata, memory = worker.observe()
    objective = {**exit_objective(memory, metadata, exit_id, source_identity),
                 "max_steps": max_steps,
                 "entry_action": {"frames": action.frames, "buttons": action.buttons,
                                  "x": action.x, "y": action.y}}
    setup_destination = objective["destination_level"]
    if arrival_level is not None:
        if (type(arrival_level) is not int or not 0 <= arrival_level <= 999 or
                arrival_level == objective["source_level"]):
            raise ValueError("invalid declared arrival level")
        objective["setup_destination_level"] = setup_destination
        objective["destination_level"] = arrival_level
        objective["required_intermediate_level"] = (
            setup_destination if arrival_level != setup_destination else None)
    (worker.root / "exit-objective.json").write_text(json.dumps(objective, indent=2))
    arrival = Arrival(objective["destination_level"])
    intermediate_seen = False
    pending_action = action
    prompt_presses = 0
    for step in range(max_steps):
        worker.act(pending_action)
        metadata, memory = worker.observe()
        mode = memory[FRONT_MODE]
        level = struct.unpack_from(">i", memory, 0xFB114)[0]
        requested_level = struct.unpack_from(">h", memory, REQUESTED_LEVEL)[0]
        region_prompt = memory[REGION_PROMPT] != 0
        pause_mode = struct.unpack_from(">b", memory, PAUSE_MODE)[0]
        intermediate_seen |= level == objective.get("required_intermediate_level")
        name = None
        if (mode == 16 and level == objective["destination_level"] and
                (objective.get("required_intermediate_level") is None or intermediate_seen)):
            # A hook pointer may still refer to the departing actor during load.
            state = decode(memory, sequence=metadata["sequence"])
            player = next((actor for actor in state.actors
                           if actor.address == metadata["player"]), None)
            name = player.name if player else None
        record = {**metadata, "step": step, "mode": mode, "level": level,
                  "player_name": name, "intermediate_seen": intermediate_seen,
                  "requested_level": requested_level,
                  "region_prompt": region_prompt, "pause_mode": pause_mode,
                  "input": {"frames": pending_action.frames,
                            "buttons": pending_action.buttons,
                            "x": pending_action.x, "y": pending_action.y}}
        with (worker.root / "exit.jsonl").open("a") as stream:
            stream.write(json.dumps(record) + "\n")
        print(json.dumps(record), flush=True)
        if arrival.accept(mode, level, name):
            worker.checkpoint("save", "e1")
            worker.observe()
            result = {**objective, "completed": True, "final_observation": record,
                      "region_prompt_presses": prompt_presses,
                      "controllability_verified": False}
            (worker.root / "exit-result.json").write_text(json.dumps(result, indent=2))
            return result
        if pending_action.buttons == 0x8000:
            pending_action = Action(12)
        elif region_prompt:
            if pause_mode != 1 or requested_level != setup_destination:
                raise ObservationError("unrecognized region-change prompt state")
            if prompt_presses >= 2:
                raise ObservationError("region-change prompt did not accept two bounded presses")
            pending_action = Action(12, buttons=0x8000)
            prompt_presses += 1
        else:
            pending_action = Action(120)
    (worker.root / "exit-failure.json").write_text(json.dumps({
        **objective, "completed": False, "classification": "arrival_not_observed",
        "last_observation": record, "steps_exhausted": max_steps,
        "region_prompt_presses": prompt_presses}, indent=2) + "\n")
    raise ObservationError("declared exit arrival not observed within budget")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--exit-id", help="semantic exit identity from phase95_world")
    parser.add_argument("--search-result", type=Path,
                        help="replay-equal search result sealing an in-flight exit checkpoint")
    parser.add_argument("--arrival-level", type=int,
                        help="declared playable arrival after the exit's intermediate level")
    parser.add_argument("--max-steps", type=int, default=100,
                        help="bounded crossing observation budget (1..100)")
    args = parser.parse_args()
    source_identity = (load_search_source(args.search_result, args.checkpoint, args.exit_id)
                       if args.search_result is not None else None)
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        cross(worker, exit_id=args.exit_id, arrival_level=args.arrival_level,
              max_steps=args.max_steps,
              source_identity=source_identity)


if __name__ == "__main__":
    main()
