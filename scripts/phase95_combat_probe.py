"""Checkpoint-isolated ordinary-input fire trials against an observed actor.

This is a diagnostic until a target-specific health/lifecycle effect and the
game's weapon hit/kill counters corroborate an encounter outcome.
"""
from dataclasses import asdict
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

from scripts.phase95_bridge import Action, Worker
from scripts.phase95_inventory import inventory, weapon_stats
from scripts.phase95_observation import decode, physical, ObservationError


R = 0x0010
Z = 0x2000


def candidates():
    settle = Action(60, buttons=R)
    fire = Action(120, buttons=R | Z)
    choices = [("neutral", (Action(120),)),
               ("fire_without_aim", (Action(120, buttons=Z),)),
               ("aim_fire", (settle, fire))]
    for axis in ("x", "y"):
        for stick in (-60, -50, 50, 60):
            pulse = Action(24, buttons=R, **{axis: stick})
            choices.append((f"aim_{axis}{stick}_fire", (settle, pulse, fire)))
    for x in (-60, 60):
        for y in (-60, 60):
            choices.append((f"aim_x{x}_y{y}_fire",
                            (settle, Action(24, buttons=R, x=x, y=y), fire)))
    for x in (-60, 60):
        for frames in (48, 72, 96, 120):
            choices.append((f"aim_x{x}_{frames}_settled_fire",
                            (settle, Action(frames, buttons=R, x=x), settle, fire)))
    for yaw_frames in (72, 96):
        for y in (-60, 60):
            for pitch_frames in (24, 48, 72):
                choices.append((f"aim_x-60_{yaw_frames}_y{y}_{pitch_frames}_fire",
                                (settle, Action(yaw_frames, buttons=R, x=-60), settle,
                                 Action(pitch_frames, buttons=R, y=y), settle, fire)))
    return choices


def target_snapshot(memory, metadata, actor_address=None):
    state = decode(memory, sequence=metadata["sequence"],
                   player_pointer=metadata["player"])
    if state.front_mode != 16 or state.player is None or memory[0xA4FC4] != 0:
        raise ObservationError("combat probe requires single-player gameplay")
    candidates_here = [actor for actor in state.actors if actor.name == "Galaxian4"]
    if actor_address is None:
        if not candidates_here:
            raise ObservationError("no observed Galaxian4 target")
        target = min(candidates_here,
                     key=lambda actor: math.dist(actor.position, state.player.position))
        actor_address = target.address
    selected = [actor for actor in candidates_here if actor.address == actor_address]
    target = selected[0] if len(selected) == 1 else None
    candidate_health = None
    if target is not None:
        base = physical(target.address, 0x6C)
        if struct.unpack_from(">h", memory, base + 0x48)[0] != 24:
            raise ObservationError("Galaxian4 control profile mismatch")
        properties = physical(struct.unpack_from(">I", memory, base + 0x4C)[0], 8)
        candidate_health = struct.unpack_from(">h", memory, properties + 6)[0]
        if not -0x1000 <= candidate_health <= 0x1000:
            raise ObservationError("target candidate health field outside probe range")
    stats = weapon_stats(memory, metadata)
    items = inventory(memory, metadata)
    return {"level_number": struct.unpack_from(">i", memory, 0xFB114)[0],
            "player_position": state.player.position,
            "player_health_raw": items["health_raw"],
            "galaxian_addresses": sorted(actor.address for actor in candidates_here),
            "target_address": actor_address, "target_present": target is not None,
            "target_position": target.position if target else None,
            "target_candidate_health_raw": candidate_health,
            "pistol_ammo": items["ammo"][0],
            "pistol_shots": stats["shots"][0],
            "pistol_hits": stats["hits"][0],
            "pistol_kills": stats["kills"][0]}


def effect(before, after):
    if before["level_number"] != after["level_number"] or \
            before["target_address"] != after["target_address"]:
        raise ObservationError("combat trial changed declared target context")
    shots = after["pistol_shots"] - before["pistol_shots"]
    hits = after["pistol_hits"] - before["pistol_hits"]
    kills = after["pistol_kills"] - before["pistol_kills"]
    ammo = before["pistol_ammo"] - after["pistol_ammo"]
    if min(shots, hits, kills, ammo) < 0:
        raise ObservationError("combat statistics are not monotonic")
    target_change = (before["target_present"] and
                     (not after["target_present"] or
                      after["target_candidate_health_raw"] <
                      before["target_candidate_health_raw"]))
    removed = sorted(set(before["galaxian_addresses"]) -
                     set(after["galaxian_addresses"]))
    return {"shots": shots, "hits": hits, "kills": kills,
            "ammo_spent": ammo, "target_change": target_change,
            "target_hit_verified": hits > 0 and target_change,
            "target_kill_verified": kills > 0 and not after["target_present"],
            "removed_galaxians": removed,
            "encounter_kill_verified": kills > 0 and bool(removed)}


def probe(worker):
    baseline_metadata, baseline_memory = worker.observe()
    baseline = target_snapshot(baseline_memory, baseline_metadata)
    if baseline["pistol_ammo"] < 15:
        raise ObservationError("insufficient ordinary pistol ammo for bounded trials")
    worker.checkpoint("save", "a0")
    worker.observe()
    baseline_hash = hashlib.sha256(baseline_memory).hexdigest()
    objective = {"kind": "jfg-phase95-combat-probe", "acceptance": False,
                 "target_name": "Galaxian4", "target_address": baseline["target_address"],
                 "baseline": baseline, "trial_count": len(candidates()),
                 "completion": "weapon kill counter increase plus observed Galaxian actor removal"}
    (worker.root / "combat-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    trials = []
    for index, (name, actions) in enumerate(candidates()):
        worker.checkpoint("load", "a0")
        restored_metadata, restored_memory = worker.observe()
        if hashlib.sha256(restored_memory).hexdigest() != baseline_hash or any(
                restored_metadata[key] != baseline_metadata[key]
                for key in ("frame", "polls", "player")):
            raise ObservationError("combat trial did not restore exact baseline")
        trajectory = []
        for action in actions:
            worker.act(action)
            metadata, memory = worker.observe()
            snapshot = target_snapshot(memory, metadata, baseline["target_address"])
            if snapshot["level_number"] != baseline["level_number"]:
                raise ObservationError("combat trial crossed an unplanned level transition")
            trajectory.append({"action": asdict(action), "observation": metadata,
                               "rdram_sha256": hashlib.sha256(memory).hexdigest(),
                               "state": snapshot})
        after = trajectory[-1]["state"]
        result = {"candidate": index, "name": name, "trajectory": trajectory,
                  "effect": effect(baseline, after)}
        trials.append(result)
        with (worker.root / "combat-trials.jsonl").open("a") as stream:
            stream.write(json.dumps(result) + "\n")
        print(json.dumps({"trial": name, "effect": result["effect"]}), flush=True)
    best = next((item for item in trials if item["effect"]["encounter_kill_verified"]), None)
    if best is None:
        best = next((item for item in trials if item["effect"]["target_hit_verified"]), None)
    if best is None:
        result = {**objective, "completed": False, "classification": "no_verified_target_hit",
                  "trials_completed": len(trials)}
        (worker.root / "combat-result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    worker.checkpoint("load", "a0")
    worker.observe()
    for expected in best["trajectory"]:
        worker.act(Action(**expected["action"]))
        metadata, memory = worker.observe()
        actual = target_snapshot(memory, metadata, baseline["target_address"])
        if (hashlib.sha256(memory).hexdigest() != expected["rdram_sha256"] or
                actual != expected["state"] or
                any(metadata[key] != expected["observation"][key]
                    for key in ("frame", "polls", "player"))):
            raise ObservationError("selected combat trial failed exact continuation")
    worker.checkpoint("save", "c1")
    worker.observe()
    result = {**objective, "completed": (best["effect"]["encounter_kill_verified"] or
                                          best["effect"]["target_hit_verified"]),
              "selected_candidate": best["candidate"], "effect": best["effect"],
              "checkpoint": "c1"}
    (worker.root / "combat-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    args = parser.parse_args()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        probe(worker)


if __name__ == "__main__":
    main()
