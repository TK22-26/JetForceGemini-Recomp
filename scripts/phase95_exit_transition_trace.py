"""Trace one sealed oracle movement edge at single-frame resolution.

This is a diagnostic, not a completed-exit predicate. It preserves each
observed level/mode/RDRAM digest so a long controller action cannot conceal a
short transition or an immediate return to the source level.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from scripts.phase95_bridge import Action, Worker
from scripts.phase95_observation import FRONT_MODE, decode, physical, ObservationError
from scripts.phase95_world import read_exit


def sample(metadata, memory, exit_id):
    level = struct.unpack_from(">i", memory, 0xFB114)[0]
    mode = memory[FRONT_MODE]
    record = {key: metadata[key] for key in ("sequence", "frame", "polls", "player")}
    record.update(level=level, mode=mode,
                  rdram_sha256=hashlib.sha256(memory).hexdigest(),
                  selected_exit_present=None, player_position=None,
                  exit_timer=None, player_exit_pointer=None)
    if mode != 16:
        return record
    try:
        state = decode(memory, sequence=metadata["sequence"],
                       player_pointer=metadata["player"] or None)
        record["player_position"] = state.player.position if state.player else None
        record["selected_exit_present"] = any(
            read_exit(memory, actor, level)["id"] == exit_id
            for actor in state.actors if actor.name == "exit")
        if state.player is not None:
            actor_base = physical(metadata["player"], 0x6C)
            private_pointer = struct.unpack_from(">I", memory, actor_base + 0x68)[0]
            private_base = physical(private_pointer, 0x5CA)
            record["exit_timer"] = struct.unpack_from(">h", memory,
                                                       private_base + 0x5C8)[0]
            record["player_exit_pointer"] = struct.unpack_from(">I", memory,
                                                                 private_base + 0xF4)[0]
    except (ObservationError, ValueError, struct.error) as error:
        record["observation_error"] = f"{type(error).__name__}: {error}"
    return record


def trace(worker, exit_id, action, frames, expected_final_sha256=None):
    if not isinstance(exit_id, str) or len(exit_id) != 64 or any(
            char not in "0123456789abcdef" for char in exit_id):
        raise ValueError("invalid exit identity")
    if type(frames) is not int or not 1 <= frames <= 120:
        raise ValueError("invalid frame budget")
    action.validate()
    if action.frames != 1:
        raise ValueError("trace action must advance one frame")
    metadata, memory = worker.observe()
    initial = sample(metadata, memory, exit_id)
    with (worker.root / "transition-frames.jsonl").open("w") as stream:
        stream.write(json.dumps({"index": 0, **initial}) + "\n")
        previous = initial
        changes = []
        for index in range(1, frames + 1):
            worker.act(action)
            metadata, memory = worker.observe()
            current = sample(metadata, memory, exit_id)
            stream.write(json.dumps({"index": index, **current}) + "\n")
            stream.flush()
            if (current["level"], current["mode"], current["selected_exit_present"]) != (
                    previous["level"], previous["mode"], previous["selected_exit_present"]):
                changes.append({"index": index, "frame": current["frame"],
                                "level": current["level"], "mode": current["mode"],
                                "selected_exit_present": current["selected_exit_present"]})
            previous = current
    equal = (previous["rdram_sha256"] == expected_final_sha256
             if expected_final_sha256 is not None else None)
    result = {"kind": "jfg-phase95-exit-transition-trace", "schema": 1,
              "acceptance": False, "exit_id": exit_id,
              "input": {"buttons": action.buttons, "x": action.x, "y": action.y},
              "frames": frames, "initial": initial, "final": previous,
              "observed_changes": changes,
              "expected_final_sha256": expected_final_sha256,
              "final_equal": equal,
              "completion_claim": False}
    (worker.root / "transition-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--exit-id", required=True)
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--x", type=int, default=0)
    parser.add_argument("--y", type=int, default=0)
    parser.add_argument("--buttons", type=int, default=0)
    parser.add_argument("--expected-final-sha256")
    args = parser.parse_args()
    private_root = Path(__file__).resolve().parents[1] / "tools" / "private"
    for path, label in ((args.output, "output"), (args.checkpoint, "checkpoint")):
        if not path.resolve().is_relative_to(private_root.resolve()):
            parser.error(f"{label} must be inside the private root")
    if args.expected_final_sha256 is not None and (
            len(args.expected_final_sha256) != 64 or any(
                char not in "0123456789abcdef" for char in args.expected_final_sha256)):
        parser.error("invalid expected final SHA-256")
    action = Action(1, buttons=args.buttons, x=args.x, y=args.y)
    action.validate()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        result = trace(worker, args.exit_id, action, args.frames,
                       args.expected_final_sha256)
    print(json.dumps({"frames": result["frames"], "observed_changes": result[
        "observed_changes"], "final_equal": result["final_equal"],
        "final_level": result["final"]["level"],
        "final_mode": result["final"]["mode"]}, sort_keys=True))


if __name__ == "__main__":
    main()
