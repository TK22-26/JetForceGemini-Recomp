"""Checkpoint-isolated BizHawk aim/input calibration; no combat success claim."""
from dataclasses import asdict
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

from scripts.phase95_bridge import Action, Worker
from scripts.phase95_inventory import inventory
from scripts.phase95_observation import decode, physical, ObservationError


def aim_state(memory, metadata):
    """Read the manual-aim fields backed by controlGetManualAim (US retail)."""
    state = decode(memory, sequence=metadata["sequence"], player_pointer=metadata["player"])
    if state.front_mode != 16 or state.player is None or memory[0xA4FC4] != 0:
        raise ObservationError("aim calibration requires active single-player gameplay")
    u32 = lambda offset: struct.unpack_from(">I", memory, offset)[0]
    if (u32(0x3AABC) != 0x27BDFFA8 or u32(0x3AC74) != 0xE60201EC or
            u32(0x3AC7C) != 0xE60E01F0 or u32(0x3AC88) != 0xE61201F0 or
            u32(0x3B09C) != 0xA618011C or u32(0x3B0C8) != 0xA60F01E2):
        raise ObservationError("manual aim code profile mismatch")
    base = physical(state.player.address, 0x6C)
    data = physical(u32(base + 0x68), 0x200)
    delta_x, delta_y, scale, offset = struct.unpack_from(">ffff", memory, data + 0x1E4)
    if (not all(math.isfinite(value) for value in (delta_x, delta_y, scale, offset)) or
            not 0 <= scale <= 5 or not -5 <= offset <= 5):
        raise ObservationError("manual aim fields outside supported range")
    first_angle, second_angle = struct.unpack_from(">hh", memory, data + 0x1FC)
    aim_yaw = struct.unpack_from(">h", memory, data + 0x11C)[0]
    aim_pitch = struct.unpack_from(">h", memory, data + 0x1E2)[0]
    control_mode = u32(0xA18B0)
    if control_mode not in (0x800A18B4, 0x800A18D8):
        raise ObservationError("unknown controller mapping")
    return {"player": state.player.address, "position": state.player.position,
            "yaw": state.player.yaw, "private_data": u32(base + 0x68),
            "manual_delta_x": delta_x, "manual_delta_y": delta_y,
            "manual_scale": scale, "manual_offset": offset,
            "manual_yaw": aim_yaw, "manual_pitch": aim_pitch,
            "aim_angle_1": first_angle, "aim_angle_2": second_angle,
            "aim_counter": memory[data + 0x1F4],
            "aim_status": memory[data + 0x1F8],
            "control_mode": "normal" if control_mode == 0x800A18B4 else "expert"}


def probe(worker):
    baseline_metadata, baseline_memory = worker.observe()
    baseline = aim_state(baseline_memory, baseline_metadata)
    level = struct.unpack_from(">i", baseline_memory, 0xFB114)[0]
    baseline_ammo = inventory(baseline_memory, baseline_metadata)["ammo"]
    worker.checkpoint("save", "a0")
    worker.observe()
    # Axes/buttons are deliberately independent: all trials start at a0.
    trials = [
        ("neutral", Action(24)),
        ("stick_right", Action(24, x=20)),
        ("stick_left", Action(24, x=-20)),
        ("r_right", Action(24, buttons=0x0010, x=20)),
        ("r_left", Action(24, buttons=0x0010, x=-20)),
        ("z_right", Action(24, buttons=0x2000, x=20)),
        ("z_left", Action(24, buttons=0x2000, x=-20)),
        ("r_right_long", Action(120, buttons=0x0010, x=60)),
        ("r_right_5", Action(120, buttons=0x0010, x=5)),
        ("r_right_10", Action(120, buttons=0x0010, x=10)),
        ("r_right_20", Action(120, buttons=0x0010, x=20)),
        ("r_right_25", Action(120, buttons=0x0010, x=25)),
        ("r_right_30", Action(120, buttons=0x0010, x=30)),
        ("r_right_40", Action(120, buttons=0x0010, x=40)),
        ("r_right_50", Action(120, buttons=0x0010, x=50)),
        ("r_up_long", Action(120, buttons=0x0010, y=60)),
        ("r_up_20", Action(120, buttons=0x0010, y=20)),
        ("r_z_right_long", Action(120, buttons=0x2010, x=60)),
    ]
    records = []
    expected_hash = hashlib.sha256(baseline_memory).hexdigest()
    for name, action in trials:
        worker.checkpoint("load", "a0")
        restored_metadata, restored_memory = worker.observe()
        if (hashlib.sha256(restored_memory).hexdigest() != expected_hash or
                any(restored_metadata[key] != baseline_metadata[key]
                    for key in ("frame", "polls", "player"))):
            raise ObservationError("aim trial did not restore exact baseline")
        worker.act(action)
        metadata, memory = worker.observe()
        if struct.unpack_from(">i", memory, 0xFB114)[0] != level:
            raise ObservationError("aim trial crossed a level transition")
        after = aim_state(memory, metadata)
        ammo = inventory(memory, metadata)["ammo"]
        record = {"trial": name, "action": asdict(action), "before": baseline,
                  "after": after, "ammo_delta": [a - b for a, b in zip(ammo, baseline_ammo)],
                  "observation": metadata, "rdram_sha256": hashlib.sha256(memory).hexdigest()}
        records.append(record)
        with (worker.root / "aim-trials.jsonl").open("a") as stream:
            stream.write(json.dumps(record) + "\n")
        print(json.dumps({"trial": name, "after": after, "ammo_delta": record["ammo_delta"]}), flush=True)
    result = {"kind": "jfg-phase95-aim-calibration", "acceptance": False,
              "checkpoint_equal": True, "level_number": level,
              "baseline_sha256": expected_hash, "trial_count": len(records),
              "limitations": "isolated input response only; no target hit or combat completion"}
    (worker.root / "aim-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def pulse_probe(worker):
    """Measure small steering pulses after R has already entered aim mode."""
    worker.observe()
    worker.act(Action(60, buttons=0x0010))
    baseline_metadata, baseline_memory = worker.observe()
    baseline = aim_state(baseline_memory, baseline_metadata)
    level = struct.unpack_from(">i", baseline_memory, 0xFB114)[0]
    if baseline["aim_counter"] == 0:
        raise ObservationError("R did not enter the observed aim state")
    worker.checkpoint("save", "a1")
    worker.observe()
    expected_hash = hashlib.sha256(baseline_memory).hexdigest()
    trials = [(f"x{stick}_{frames}", Action(frames, buttons=0x0010, x=stick))
              for stick in (50, 60) for frames in (6, 12, 24, 48, 96)]
    trials += [(f"y{stick}_{frames}", Action(frames, buttons=0x0010, y=stick))
               for stick in (50, 60) for frames in (12, 24, 48)]
    records = []
    for name, action in trials:
        worker.checkpoint("load", "a1")
        restored_metadata, restored_memory = worker.observe()
        if (hashlib.sha256(restored_memory).hexdigest() != expected_hash or
                any(restored_metadata[key] != baseline_metadata[key]
                    for key in ("frame", "polls", "player"))):
            raise ObservationError("aim pulse did not restore exact baseline")
        worker.act(action)
        metadata, memory = worker.observe()
        if struct.unpack_from(">i", memory, 0xFB114)[0] != level:
            raise ObservationError("aim pulse crossed a level transition")
        after = aim_state(memory, metadata)
        record = {"trial": name, "action": asdict(action), "before": baseline,
                  "after": after,
                  "yaw_delta": ((after["yaw"] - baseline["yaw"] + 32768) % 65536) - 32768,
                  "pitch_delta": after["manual_pitch"] - baseline["manual_pitch"],
                  "observation": metadata, "rdram_sha256": hashlib.sha256(memory).hexdigest()}
        records.append(record)
        with (worker.root / "aim-pulses.jsonl").open("a") as stream:
            stream.write(json.dumps(record) + "\n")
        print(json.dumps({"trial": name, "yaw_delta": record["yaw_delta"],
                          "pitch_delta": record["pitch_delta"]}), flush=True)
    result = {"kind": "jfg-phase95-aim-pulse-calibration", "acceptance": False,
              "checkpoint_equal": True, "level_number": level,
              "baseline_sha256": expected_hash, "trial_count": len(records),
              "limitations": "short input response only; no target hit or combat completion"}
    (worker.root / "aim-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--pulse", action="store_true", help="calibrate short aim-held pulses")
    args = parser.parse_args()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"), args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        (pulse_probe if args.pulse else probe)(worker)


if __name__ == "__main__":
    main()
