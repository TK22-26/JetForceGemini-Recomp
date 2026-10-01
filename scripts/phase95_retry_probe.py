"""Test bounded ordinary retry-button candidates from a sealed zero-health state."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from scripts.phase95_bridge import Action, Worker
from scripts.phase95_inventory import inventory
from scripts.phase95_observation import decode, ObservationError


TRIALS = (("a", Action(12, buttons=0x8000)),
          ("start", Action(12, buttons=0x1000)),
          ("b", Action(12, buttons=0x4000)),
          ("move", Action(120, x=60, y=60)))


def observe(worker, trial, phase):
    metadata, memory = worker.observe()
    try:
        state = decode(memory, sequence=metadata["sequence"],
                       player_pointer=metadata["player"] or None)
    except ObservationError:
        state = decode(memory, sequence=metadata["sequence"])
    health = None
    if state.front_mode == 16 and state.player is not None:
        try:
            health = inventory(memory, metadata)["health_raw"]
        except ObservationError:
            pass
    record = {"trial": trial, "phase": phase, "frame": metadata["frame"],
              "polls": metadata["polls"], "mode": state.front_mode,
              "level": struct.unpack_from(">i", memory, 0xFB114)[0],
              "player": state.player.address if state.player else None,
              "player_name": state.player.name if state.player else None,
              "position": state.player.position if state.player else None,
              "health_raw": health,
              "rdram_sha256": hashlib.sha256(memory).hexdigest()}
    with (worker.root / "retry-observations.jsonl").open("a") as stream:
        stream.write(json.dumps(record) + "\n")
    print(json.dumps({key: record[key] for key in
                      ("trial", "phase", "frame", "mode", "level", "health_raw")}),
          flush=True)
    return record


def probe(worker, *, settle_steps=0):
    baseline = observe(worker, "baseline", "start")
    if baseline["health_raw"] != 0 or baseline["mode"] != 16:
        raise ObservationError("retry probe requires a zero-health gameplay checkpoint")
    if type(settle_steps) is not int or not 0 <= settle_steps <= 60:
        raise ValueError("invalid zero-health settling budget")
    if settle_steps:
        for index in range(settle_steps):
            worker.act(Action(120))
            baseline = observe(worker, "baseline", f"settle-{index + 1}")
            if baseline["health_raw"] != 0 or baseline["mode"] != 16:
                raise ObservationError("zero-health state changed during retry settling")
        worker.checkpoint("save", "d1")
        baseline = observe(worker, "baseline", "sealed-settle")
    slot = "d1" if settle_steps else "f0"
    objective = {"kind": "jfg-phase95-retry-input-probe", "acceptance": False,
                 "source_level": baseline["level"], "source_frame": baseline["frame"],
                 "settle_steps": settle_steps,
                 "candidates": [{"name": name, "buttons": action.buttons,
                                 "x": action.x, "y": action.y,
                                 "press_frames": action.frames, "release_frames": 120}
                                for name, action in TRIALS],
                 "completion": "input-triggered player loss followed by three stable same-level positive-health playerBoy observations"}
    (worker.root / "retry-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    results = []
    for name, action in TRIALS:
        worker.checkpoint("load", slot)
        restored = observe(worker, name, "restore")
        if restored["rdram_sha256"] != baseline["rdram_sha256"]:
            raise ObservationError("retry trial did not restore exact checkpoint")
        worker.act(action)
        pressed = observe(worker, name, "pressed")
        worker.act(Action(120))
        released = observe(worker, name, "released")
        follow = []
        stable = 0
        if released["player"] is None:
            for index in range(20):
                worker.act(Action(120))
                item = observe(worker, name, f"follow-{index + 1}")
                follow.append(item)
                arrived = (item["mode"] == 16 and
                           item["level"] == baseline["level"] and
                           item["player_name"] == "playerBoy" and
                           item["health_raw"] is not None and
                           item["health_raw"] > 0)
                stable = stable + 1 if arrived else 0
                if stable >= 3:
                    break
        results.append({"name": name, "pressed": pressed, "released": released,
                        "follow": follow, "stable_arrival_count": stable,
                        "retry_verified": released["player"] is None and stable >= 3})
    summary = {**objective, "completed": True, "trials": results,
               "death_verified": any(trial["retry_verified"] for trial in results),
               "retry_verified": any(trial["retry_verified"] for trial in results)}
    (worker.root / "retry-result.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--settle-steps", type=int, default=0)
    args = parser.parse_args()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        probe(worker, settle_steps=args.settle_steps)


if __name__ == "__main__":
    main()
