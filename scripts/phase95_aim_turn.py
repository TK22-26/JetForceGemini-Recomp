"""Checkpoint-lookahead yaw/pitch steering with ordinary controller input."""
from dataclasses import asdict
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

from scripts.phase95_aim import aim_state
from scripts.phase95_bridge import Action, Worker
from scripts.phase95_observation import ObservationError


def signed_yaw_error(target, current):
    if type(target) is not int or type(current) is not int or not 0 <= target < 65536 or not 0 <= current < 65536:
        raise ValueError("invalid yaw angle")
    return ((target - current + 32768) % 65536) - 32768


def aim_settled(state):
    values = (state["manual_delta_x"], state["manual_delta_y"])
    return all(math.isfinite(value) and abs(value) < 1 for value in values)


def candidates(axis="yaw"):
    if axis not in ("yaw", "pitch"):
        raise ValueError("unknown aim axis")
    settle = Action(60, buttons=0x0010)
    return [(Action(frames, buttons=0x0010, **({"x": stick} if axis == "yaw" else {"y": stick})),
             settle)
            for frames in (6, 12, 24, 30, 36, 42, 48)
            for stick in (-60, -50, 50, 60)] + [(settle,)]


def turn(worker, target, *, axis="yaw", tolerance=256, max_steps=12,
         slot_prefix="b", seal_slot="c1", output_prefix="aim"):
    if axis == "yaw":
        if type(target) is not int or not 0 <= target < 65536:
            raise ValueError("target yaw must be uint16")
        error = lambda current: abs(signed_yaw_error(target, current))
    elif axis == "pitch":
        if type(target) is not int or not -16384 <= target <= 16384:
            raise ValueError("target pitch outside supported range")
        error = lambda current: abs(target - current)
    else:
        raise ValueError("unknown aim axis")
    if not 1 <= tolerance <= 4096 or not 1 <= max_steps <= 30:
        raise ValueError("invalid aim steering budget")
    if (slot_prefix not in "0123456789abcdef" or
            not 1 <= len(seal_slot) <= 32 or
            any(char not in "0123456789abcdef" for char in seal_slot) or
            not output_prefix or not output_prefix.replace("-", "").isalnum()):
        raise ValueError("invalid aim artifact namespace")
    field = "yaw" if axis == "yaw" else "manual_pitch"
    worker.observe()
    worker.act(Action(60, buttons=0x0010))
    metadata, memory = worker.observe()
    state = aim_state(memory, metadata)
    if state["aim_counter"] == 0:
        raise ObservationError("R did not enter the observed aim state")
    level = struct.unpack_from(">i", memory, 0xFB114)[0]

    def execute(actions):
        trajectory = []
        for action in actions:
            worker.act(action)
            action_metadata, action_memory = worker.observe()
            if struct.unpack_from(">i", action_memory, 0xFB114)[0] != level:
                raise ObservationError("aim lookahead crossed a level transition")
            action_state = aim_state(action_memory, action_metadata)
            trajectory.append({"observation": {key: action_metadata[key]
                                               for key in ("frame", "polls", "player")},
                               "rdram_sha256": hashlib.sha256(action_memory).hexdigest(),
                               "yaw": action_state["yaw"],
                               "pitch": action_state["manual_pitch"]})
        return action_metadata, action_memory, action_state, trajectory

    objective = {"kind": f"jfg-phase95-{axis}-steering", "acceptance": False,
                 f"target_{axis}": target, "tolerance": tolerance,
                 "max_steps": max_steps, f"initial_{axis}": state[field],
                 "level_number": level, "limitations": "one-axis response only; no target hit"}
    (worker.root / f"{output_prefix}-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    for step in range(max_steps + 1):
        before = error(state[field])
        if before <= tolerance and aim_settled(state):
            worker.checkpoint("save", seal_slot)
            worker.observe()
            result = {**objective, "completed": True, "steps": step,
                      f"final_{axis}": state[field], "final_error": before}
            (worker.root / f"{output_prefix}-result.json").write_text(json.dumps(result, indent=2) + "\n")
            return result
        if step == max_steps:
            break
        slot = f"{slot_prefix}{step:04x}"
        worker.checkpoint("save", slot)
        worker.observe()
        trials = []
        for index, actions in enumerate(candidates(axis)):
            worker.checkpoint("load", slot)
            worker.observe()
            trial_metadata, trial_memory, trial_state, trajectory = execute(actions)
            record = {"step": step, "candidate": index,
                      "actions": [asdict(action) for action in actions],
                      axis: trial_state[field],
                      "manual_delta": trial_state["manual_delta_x" if axis == "yaw" else "manual_delta_y"],
                      "error": error(trial_state[field]),
                      "observation": trial_metadata,
                      "rdram_sha256": hashlib.sha256(trial_memory).hexdigest(),
                      "trajectory": trajectory}
            trials.append(record)
            with (worker.root / f"{output_prefix}-trials.jsonl").open("a") as stream:
                stream.write(json.dumps(record) + "\n")
        best = min(trials, key=lambda item: (item["error"], item["candidate"]))
        if best["error"] >= before:
            result = {**objective, "completed": False, "steps": step,
                      f"final_{axis}": state[field], "final_error": before,
                      "classification": "no_improving_input"}
            (worker.root / f"{output_prefix}-result.json").write_text(json.dumps(result, indent=2) + "\n")
            raise ObservationError("aim lookahead found no improving input")
        worker.checkpoint("load", slot)
        worker.observe()
        metadata, memory, state, trajectory = execute(candidates(axis)[best["candidate"]])
        if (trajectory != best["trajectory"] or
                hashlib.sha256(memory).hexdigest() != best["rdram_sha256"] or
                any(metadata[key] != best["observation"][key]
                    for key in ("frame", "polls", "player"))):
            raise ObservationError("selected aim input failed exact continuation check")
        with (worker.root / f"{output_prefix}-selected.jsonl").open("a") as stream:
            stream.write(json.dumps(best) + "\n")
        print(json.dumps({"aim_step": step, axis: state[field],
                          "error": best["error"]}), flush=True)
    result = {**objective, "completed": False, "steps": max_steps,
              f"final_{axis}": state[field],
              "final_error": error(state[field]),
              "classification": "budget_exhausted"}
    (worker.root / f"{output_prefix}-result.json").write_text(json.dumps(result, indent=2) + "\n")
    raise ObservationError("aim steering budget exhausted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--yaw-offset", type=int)
    parser.add_argument("--pitch-offset", type=int)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    args = parser.parse_args()
    if args.yaw_offset is None and args.pitch_offset is None:
        parser.error("provide --yaw-offset, --pitch-offset, or both")
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"), args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        metadata, memory = worker.observe()
        state = aim_state(memory, metadata)
        yaw_target = (state["yaw"] + args.yaw_offset) % 65536 if args.yaw_offset is not None else None
        pitch_target = state["manual_pitch"] + args.pitch_offset if args.pitch_offset is not None else None
        if pitch_target is not None and not -16384 <= pitch_target <= 16384:
            parser.error("requested pitch is outside the supported range")
        if args.yaw_offset is not None:
            turn(worker, yaw_target)
        if args.pitch_offset is not None:
            turn(worker, pitch_target, axis="pitch",
                 slot_prefix="d" if yaw_target is not None else "b",
                 seal_slot="c2" if yaw_target is not None else "c1",
                 output_prefix="pitch" if yaw_target is not None else "aim")
        if yaw_target is not None and pitch_target is not None:
            metadata, memory = worker.observe()
            final = aim_state(memory, metadata)
            yaw_error = abs(signed_yaw_error(yaw_target, final["yaw"]))
            pitch_error = abs(pitch_target - final["manual_pitch"])
            result = {"kind": "jfg-phase95-combined-aim", "acceptance": False,
                      "completed": yaw_error <= 256 and pitch_error <= 256 and
                                   aim_settled(final),
                      "target_yaw": yaw_target, "target_pitch": pitch_target,
                      "final_yaw": final["yaw"], "final_pitch": final["manual_pitch"],
                      "yaw_error": yaw_error, "pitch_error": pitch_error,
                      "checkpoint_slot": "c2",
                      "limitations": "angle alignment only; no observed target hit"}
            (worker.root / "combined-aim-result.json").write_text(json.dumps(result, indent=2) + "\n")
            if not result["completed"]:
                raise ObservationError("combined aim endpoint failed settled angle checks")


if __name__ == "__main__":
    main()
