"""Bounded NPC dialogue probe from a sealed oracle frontier.

Only the game's selected-speaker pointer establishes that conversation started.
"""
import argparse
import json
from pathlib import Path
import struct

from scripts.phase95_bridge import Worker, Action
from scripts.phase95_observation import decode, physical, ObservationError


def hint_state(memory, sequence, player, actor_name="MrHints2"):
    if actor_name not in ("MrHints2", "KingBear"):
        raise ObservationError("unsupported dialogue actor")
    observation = decode(memory, sequence=sequence, player_pointer=player)
    hints = [actor for actor in observation.actors if actor.name == actor_name]
    if observation.front_mode != 16 or observation.player is None or len(hints) != 1:
        raise ObservationError("hint probe lost its gameplay context")
    actor = hints[0]
    address = physical(actor.address, 0x6C)
    # objObjectsTick dispatches actor+0x48 through this resident switch.
    # Verify the actual relocated call, not just an actor's display name.
    u32 = lambda offset: struct.unpack_from(">I", memory, offset)[0]
    if struct.unpack_from(">12I", memory, 0xFC80) != (
            0x848B0048, 0, 0x256CFFFE, 0x2D8100AD, 0x10200205,
            0x000C6080, 0x3C01800B, 0x002C0821, 0x8C2CB24C, 0,
            0x01800008, 0):
        raise ObservationError("dialogue dispatch profile mismatch")
    control = struct.unpack_from(">h", memory, address + 0x48)[0]
    if not 2 <= control <= 174:
        raise ObservationError("dialogue control outside dispatch table")
    table = physical(u32(0xFEAA0), 33 * 32)
    module_pointer = u32(table + 32 * 32)
    module = physical(module_pointer, 0x2554)
    if struct.unpack_from(">6I", memory, module) != (
            0x27BDFFA8, 0xAFBF003C, 0xAFB10038, 0xAFB00034, 0x8C900068, 0x848E0000):
        raise ObservationError("dialogue overlay profile mismatch")
    dispatch = physical(u32(0xAB24C + (control - 2) * 4), 4)
    expected_call = 0x0C000000 | (((module_pointer + 0x2E8) >> 2) & 0x03FFFFFF)
    if u32(dispatch) != expected_call:
        raise ObservationError("actor is not dispatched to mrhintsControl")
    # mrHintsTalk reads the selected speaker through a relocated LUI/LW pair.
    # Nonzero actor modes alone also describe roaming and reactions.
    high, low = struct.unpack_from(">2I", memory, module + 0x2540)
    if high & 0xFFFF0000 != 0x3C070000 or low & 0xFFFF0000 != 0x8CE70000:
        raise ObservationError("dialogue speaker accessor mismatch")
    speaker_global = ((high & 0xFFFF) << 16) + struct.unpack(">h", struct.pack(">H", low & 0xFFFF))[0]
    speaker = u32(physical(speaker_global, 4))
    if speaker and speaker not in {a.address for a in observation.actors}:
        raise ObservationError("dialogue speaker is not a current actor")
    data = struct.unpack_from(">I", memory, address + 0x68)[0]
    offset = physical(data, 0x38)
    mode = memory[offset]
    if mode > 18:
        raise ObservationError("unknown hint control mode")
    return {"actor": actor.address, "actor_name": actor_name, "control": control,
            "private_data": data, "mode": mode,
            "speaker": speaker, "conversation_active": speaker == actor.address,
            "state_tail_hex": memory[offset + 0x30:offset + 0x38].hex(),
            "player_position": observation.player.position if observation.player else None,
            "hint_position": actor.position}


class DialogueProbe:
    def __init__(self):
        self.active_seen = False
        self.idle_samples = 0
        self.release = False

    def choose(self, mode, *, conversation_active):
        if type(mode) is not int or not 0 <= mode <= 18:
            raise ObservationError("invalid hint mode")
        if type(conversation_active) is not bool:
            raise ObservationError("invalid conversation selection")
        self.active_seen |= conversation_active
        self.idle_samples = (self.idle_samples + 1 if self.active_seen and
                             not conversation_active and mode in (0, 1, 2) else 0)
        if self.idle_samples >= 3:
            return None
        if self.idle_samples or self.release:
            self.release = False
            return Action(48)
        self.release = True
        return Action(12, buttons=0x8000)


def probe(worker, actor_name="MrHints2", *, max_steps=120):
    if actor_name not in ("MrHints2", "KingBear") or not 1 <= max_steps <= 120:
        raise ValueError("invalid bounded dialogue objective")
    policy = DialogueProbe()
    for step in range(max_steps):
        metadata, memory = worker.observe()
        state = hint_state(memory, metadata["sequence"], metadata["player"], actor_name)
        record = {**metadata, **state, "step": step}
        with (worker.root / "dialogue.jsonl").open("a") as stream:
            stream.write(json.dumps(record) + "\n")
        print(json.dumps(record), flush=True)
        action = policy.choose(state["mode"], conversation_active=state["conversation_active"])
        if action is None:
            worker.checkpoint("save", "d1")
            worker.observe()
            result = {"kind": "jfg-phase95-dialogue-probe", "acceptance": False,
                      "active_then_idle": True, "steps": step,
                      "progression_verified": False}
            (worker.root / "dialogue-result.json").write_text(json.dumps(result) + "\n")
            return result
        worker.act(action)
    (worker.root / "dialogue-result.json").write_text(json.dumps({
        "kind": "jfg-phase95-dialogue-probe", "acceptance": False,
        "completed": False, "classification": "no_selected_conversation",
        "actor_name": actor_name, "steps": max_steps,
        "active_seen": policy.active_seen,
        "progression_verified": False}) + "\n")
    raise ObservationError("dialogue probe budget exhausted without selected conversation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--actor", choices=("MrHints2", "KingBear"), default="MrHints2")
    parser.add_argument("--approach", action="store_true",
                        help="navigate to the observed NPC before the bounded dialogue probe")
    parser.add_argument("--max-steps", type=int, default=120)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    args = parser.parse_args()
    if not 1 <= args.max_steps <= 120:
        parser.error("max steps must be 1..120")
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        if args.approach:
            from scripts.phase95_navigation import navigate
            metadata, memory = worker.observe()
            initial = hint_state(memory, metadata["sequence"], metadata["player"], args.actor)
            # An already active conversation needs no approach. Proximity is
            # only a navigation endpoint, never proof of an interaction.
            if not initial["conversation_active"]:
                navigate(worker, "surface-waypoint", waypoint=initial["hint_position"],
                         radius=30, precision=True)
        probe(worker, args.actor, max_steps=args.max_steps)


if __name__ == "__main__":
    main()
