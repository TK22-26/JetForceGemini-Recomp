"""Checkpoint-isolated button sweep for ordinary jump/traversal calibration."""
from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import struct

from scripts.phase95_bridge import Action, Worker
from scripts.phase95_inventory import inventory
from scripts.phase95_observation import decode, ObservationError


BUTTONS = (("a", 0x8000), ("b", 0x4000), ("c_right", 0x0008),
           ("c_left", 0x0004), ("r", 0x0010), ("z", 0x2000))


def probe(worker):
    metadata, memory = worker.observe()
    initial = decode(memory, sequence=metadata["sequence"], player_pointer=metadata["player"])
    if initial.front_mode != 16 or initial.player is None:
        raise ObservationError("jump calibration requires active player")
    initial_ammo = inventory(memory, metadata)["ammo"]
    level = struct.unpack_from(">i", memory, 0xFB114)[0]
    baseline_hash = hashlib.sha256(memory).hexdigest()
    worker.checkpoint("save", "a0")
    worker.observe()
    records = []
    for name, button in BUTTONS:
        worker.checkpoint("load", "a0")
        restored, raw = worker.observe()
        if (hashlib.sha256(raw).hexdigest() != baseline_hash or
                any(restored[key] != metadata[key] for key in ("frame", "polls", "player"))):
            raise ObservationError("jump button trial failed checkpoint restoration")
        samples = []
        for action in (Action(12, buttons=button), Action(12, buttons=button),
                       Action(12, buttons=button), Action(24)):
            worker.act(action)
            observed, raw = worker.observe()
            state = decode(raw, sequence=observed["sequence"], player_pointer=observed["player"])
            if state.front_mode != 16 or state.player is None or struct.unpack_from(">i", raw, 0xFB114)[0] != level:
                raise ObservationError("jump trial left declared gameplay level")
            samples.append({"action": asdict(action), "position": state.player.position,
                            "frame": observed["frame"], "polls": observed["polls"],
                            "rdram_sha256": hashlib.sha256(raw).hexdigest()})
        after_ammo = inventory(raw, observed)["ammo"]
        record = {"button": name, "mask": button, "initial_position": initial.player.position,
                  "samples": samples,
                  "max_sampled_rise": max(item["position"][1] - initial.player.position[1]
                                          for item in samples),
                  "ammo_delta": [a - b for a, b in zip(after_ammo, initial_ammo)]}
        records.append(record)
        with (worker.root / "jump-trials.jsonl").open("a") as stream:
            stream.write(json.dumps(record) + "\n")
        print(json.dumps({"button": name, "max_sampled_rise": record["max_sampled_rise"],
                          "ammo_delta_0": record["ammo_delta"][0]}), flush=True)
    result = {"kind": "jfg-phase95-jump-button-calibration", "acceptance": False,
              "checkpoint_equal": True, "level_number": level, "trial_count": len(records),
              "limitations": "sampled button response only; no ledge crossing or enemy interaction"}
    (worker.root / "jump-result.json").write_text(json.dumps(result, indent=2) + "\n")
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
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"), args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        probe(worker)


if __name__ == "__main__":
    main()
