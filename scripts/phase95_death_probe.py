"""Observe a bounded natural-damage/death path using ordinary neutral input."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from scripts.phase95_bridge import Action, Worker
from scripts.phase95_inventory import inventory
from scripts.phase95_observation import decode, ObservationError


def probe(worker, *, max_steps=80, unchanged_budget=20,
          post_depletion_steps=0):
    if not 1 <= max_steps <= 200 or not 1 <= unchanged_budget <= max_steps:
        raise ValueError("invalid bounded death-probe budget")
    if type(post_depletion_steps) is not int or not 0 <= post_depletion_steps <= 100:
        raise ValueError("invalid post-depletion observation budget")
    metadata, memory = worker.observe()
    state = decode(memory, sequence=metadata["sequence"],
                   player_pointer=metadata["player"])
    if state.front_mode != 16 or state.player is None:
        raise ObservationError("death probe requires active player")
    baseline = inventory(memory, metadata)
    source_level = struct.unpack_from(">i", memory, 0xFB114)[0]
    objective = {"kind": "jfg-phase95-natural-death-probe", "acceptance": False,
                 "source_level": source_level, "initial_health_raw": baseline["health_raw"],
                 "max_steps": max_steps, "unchanged_budget": unchanged_budget,
                 "post_depletion_steps": post_depletion_steps,
                 "action": {"frames": 120, "buttons": 0, "x": 0, "y": 0},
                 "completion": "observed health depletion or loss of player gameplay; not death/retry verification"}
    (worker.root / "death-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    health = baseline["health_raw"]
    unchanged = 0
    for step in range(max_steps):
        worker.act(Action(120))
        metadata, memory = worker.observe()
        try:
            state = decode(memory, sequence=metadata["sequence"],
                           player_pointer=metadata["player"] or None)
        except ObservationError:
            # The controlPlayer hook may hold a departing actor pointer during
            # a death/loading transition. Keep observing, but do not infer death.
            state = decode(memory, sequence=metadata["sequence"])
        level = struct.unpack_from(">i", memory, 0xFB114)[0]
        current_health = None
        if state.front_mode == 16 and state.player is not None:
            try:
                current_health = inventory(memory, metadata)["health_raw"]
            except ObservationError:
                pass
        record = {"step": step + 1, "frame": metadata["frame"],
                  "polls": metadata["polls"], "mode": state.front_mode,
                  "level": level, "player": state.player.address if state.player else None,
                  "position": state.player.position if state.player else None,
                  "health_raw": current_health,
                  "rdram_sha256": hashlib.sha256(memory).hexdigest()}
        with (worker.root / "death-observations.jsonl").open("a") as stream:
            stream.write(json.dumps(record) + "\n")
        print(json.dumps({"step": step + 1, "frame": metadata["frame"],
                          "mode": state.front_mode, "health_raw": current_health}), flush=True)
        if current_health is not None:
            unchanged = unchanged + 1 if current_health == health else 0
            health = current_health
        depleted = current_health is not None and current_health <= 0
        if depleted or state.front_mode != 16 or level != source_level:
            after_zero = []
            if depleted and post_depletion_steps:
                worker.checkpoint("save", "d0")
                worker.observe()
                for offset in range(post_depletion_steps):
                    worker.act(Action(120))
                    post_meta, post_memory = worker.observe()
                    try:
                        post_state = decode(post_memory, sequence=post_meta["sequence"],
                                            player_pointer=post_meta["player"] or None)
                    except ObservationError:
                        post_state = decode(post_memory, sequence=post_meta["sequence"])
                    post_level = struct.unpack_from(">i", post_memory, 0xFB114)[0]
                    post_health = None
                    if post_state.front_mode == 16 and post_state.player is not None:
                        try:
                            post_health = inventory(post_memory, post_meta)["health_raw"]
                        except ObservationError:
                            pass
                    item = {"step_after_zero": offset + 1, "frame": post_meta["frame"],
                            "mode": post_state.front_mode, "level": post_level,
                            "player": post_state.player.address if post_state.player else None,
                            "position": post_state.player.position if post_state.player else None,
                            "health_raw": post_health,
                            "rdram_sha256": hashlib.sha256(post_memory).hexdigest()}
                    after_zero.append(item)
                    with (worker.root / "death-after-zero.jsonl").open("a") as stream:
                        stream.write(json.dumps(item) + "\n")
                    print(json.dumps({"after_zero": offset + 1,
                                      "frame": item["frame"], "mode": item["mode"],
                                      "health_raw": post_health}), flush=True)
                    if (post_health is not None and post_health > 0 and
                            post_state.front_mode == 16 and post_level == source_level and
                            post_state.player is not None):
                        break
            result = {**objective, "completed": True, "last_observation": record,
                      "health_depleted_observed": depleted,
                      "death_verified": False,
                      "gameplay_loss_observed": state.front_mode != 16 or level != source_level,
                      "after_zero": after_zero,
                      "retry_verified": False}
            (worker.root / "death-result.json").write_text(json.dumps(result, indent=2) + "\n")
            return result
        if unchanged >= unchanged_budget:
            break
    result = {**objective, "completed": False,
              "reason": "health did not reach zero within bounded neutral observations",
              "steps_observed": step + 1, "final_health_raw": health,
              "retry_verified": False}
    (worker.root / "death-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--max-steps", type=int, default=80)
    parser.add_argument("--unchanged-budget", type=int, default=20)
    parser.add_argument("--post-depletion-steps", type=int, default=0)
    args = parser.parse_args()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        probe(worker, max_steps=args.max_steps,
              unchanged_budget=args.unchanged_budget,
              post_depletion_steps=args.post_depletion_steps)


if __name__ == "__main__":
    main()
