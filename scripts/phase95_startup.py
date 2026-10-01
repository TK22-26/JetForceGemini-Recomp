"""State-aware startup driver; currently stops for keyboard-state validation.

This is a bounded diagnostic, not Phase 9.5 gameplay acceptance.
"""
import argparse
import json
from pathlib import Path
import struct
import time

from scripts.phase95_bridge import Action, Worker
from scripts.phase95_observation import FRONT_MODE, RDRAM_SIZE, ObservationError, decode
from scripts.phase95_keyboard import keyboard


class Startup:
    def __init__(self, complete_label=False, gameplay=False):
        self.last_sequence = -1
        self.release = False
        self.complete_label = complete_label or gameplay
        self.gameplay = gameplay
        self.saw_keyboard = False
        self.previous_key = None
        self.unchanged_key = 0

    def choose(self, sequence: int, memory: bytes, player_pointer=None) -> Action | None:
        if type(sequence) is not int or sequence <= self.last_sequence:
            raise ObservationError("stale startup observation")
        if len(memory) != RDRAM_SIZE:
            raise ObservationError("incomplete startup observation")
        self.last_sequence = sequence
        mode = memory[FRONT_MODE]
        if mode == 24 and not self.complete_label:
            return None  # diagnostic endpoint, NOT gameplay completion
        if self.saw_keyboard and mode != 24 and not self.gameplay:
            return None
        if self.gameplay and mode == 16:
            if not player_pointer:
                return Action(30)
            observation = decode(memory, sequence=sequence, player_pointer=player_pointer)
            if observation.player.name != "playerBoy":
                raise ObservationError("unexpected startup player")
            return None
        if self.release:
            self.release = False
            return Action(30)
        if mode in (0, 2):
            return Action(120)
        if mode == 24:
            state = keyboard(memory)
            if state is None:
                return Action(30)
            self.saw_keyboard = True
            self.release = True
            if state["submode"] == 0:
                return Action(12, buttons=0x8000)
            if state["submode"] == 1:
                if state["label_length"] == 0 or state["key"] == 40:
                    return Action(12, buttons=0x8000)
                self.unchanged_key = self.unchanged_key + 1 if self.previous_key == state["key"] else 0
                self.previous_key = state["key"]
                if self.unchanged_key >= 8:
                    raise ObservationError("keyboard navigation unresponsive after bounded retries")
                # Horizontal selection wraps over 41 keys, including END (40).
                direction = -80 if state["key"] < 20 else 80
                if self.unchanged_key >= 4:
                    direction = -direction
                return Action(12 if self.unchanged_key >= 2 else 4, x=direction)
            self.release = False
            return Action(30)  # menu animation; bounded by runner budget
        if mode == 3 or (self.gameplay and mode == 5):
            self.release = True
            return Action(12, buttons=0x8000)
        raise ObservationError(f"unsupported startup mode {mode}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--complete-label", action="store_true")
    parser.add_argument("--gameplay", action="store_true")
    parser.add_argument("--calibrate-movement", action="store_true")
    parser.add_argument("--verify-gameplay-checkpoint", action="store_true")
    parser.add_argument("--navigate-target", choices=("longwoodbridge", "MrHints2", "exit"))
    parser.add_argument("--resume-checkpoint", type=Path)
    parser.add_argument("--exit-id", help="semantic exit identity from phase95_world")
    parser.add_argument("--navigation-jump", action="store_true")
    args = parser.parse_args()
    args.verify_gameplay_checkpoint = args.verify_gameplay_checkpoint or bool(args.navigate_target)
    args.calibrate_movement = args.calibrate_movement or args.verify_gameplay_checkpoint
    args.gameplay = args.gameplay or args.calibrate_movement
    policy = Startup(complete_label=args.complete_label, gameplay=args.gameplay)
    started = time.monotonic()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        if args.resume_checkpoint:
            if not args.navigate_target:
                parser.error("checkpoint resume currently requires a navigation target")
            from scripts.phase95_navigation import navigate
            worker.observe()
            worker.import_checkpoint(args.resume_checkpoint)
            navigate(worker, args.navigate_target, exit_id=args.exit_id, jump=args.navigation_jump)
            return
        for _ in range(700):
            if time.monotonic() - started > 600:
                raise TimeoutError("startup wall-time budget exhausted")
            metadata, memory = worker.observe()
            record = {**metadata, "front_mode": memory[FRONT_MODE],
                      "level_number": struct.unpack_from(">i", memory, 0xFB114)[0],
                      "guest_controller_0": memory[0xFB0C0:0xFB0C6].hex(),
                      "keyboard": keyboard(memory)}
            with (worker.root / "startup.jsonl").open("a") as stream:
                stream.write(json.dumps(record) + "\n")
            print(json.dumps(record), flush=True)
            action = policy.choose(metadata["sequence"], memory, metadata["player"] or None)
            if action is None:
                (worker.root / "keyboard-entry.rdram").write_bytes(memory)
                (worker.root / "startup-result.json").write_text(json.dumps({
                    "kind": "jfg-phase95-startup-diagnostic", "acceptance": False,
                    "endpoint": "player-mode-16" if args.gameplay else
                        "left-name-interface" if args.complete_label else "front-mode-24",
                    "state": record}) + "\n")
                if args.calibrate_movement:
                    from scripts.phase95_movement import measure
                    measure(worker, verify_checkpoint=args.verify_gameplay_checkpoint)
                if args.navigate_target:
                    from scripts.phase95_navigation import navigate
                    worker.checkpoint("load", "a1")
                    worker.observe()
                    navigate(worker, args.navigate_target, exit_id=args.exit_id, jump=args.navigation_jump)
                return
            worker.act(action)
        raise TimeoutError("startup action budget exhausted")


if __name__ == "__main__":
    main()
