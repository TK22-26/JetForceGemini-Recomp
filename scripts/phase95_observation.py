"""Read-only US-retail RDRAM observations for the autonomous gameplay driver.

Offsets are diagnostic facts shared with phase9_bizhawk_oracle.lua. This module
does not infer health, hostility, or traversability from unverified actor bytes.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import struct

RDRAM_SIZE = 0x400000
ACTOR_LIST = 0xF2CA4
ACTOR_COUNT = 0xF2CA8
FRONT_MODE = 0xA51B0
RNG = 0xA33E4
MAX_ACTORS = 1024


class ObservationError(ValueError):
    """Unsafe or unsupported state; the controller must not act on it."""


def physical(pointer: int, size: int, *, aligned: bool = True) -> int:
    if type(pointer) is not int or type(size) is not int or size <= 0:
        raise ObservationError("invalid pointer/size type")
    if not (0x80000000 <= pointer < 0x80400000 or
            0xA0000000 <= pointer < 0xA0400000):
        raise ObservationError(f"not a supported RDRAM pointer: {pointer:#x}")
    offset = pointer & 0x1FFFFFFF
    if offset + size > RDRAM_SIZE or (aligned and offset % 4):
        raise ObservationError("unaligned or out-of-range RDRAM span")
    return offset


@dataclass(frozen=True)
class Actor:
    address: int
    header: int
    name: str
    yaw: int
    position: tuple[float, float, float]


@dataclass(frozen=True)
class Observation:
    schema: int
    profile: str
    sequence: int
    front_mode: int
    rng: int
    actors: tuple[Actor, ...]
    player: Actor | None
    unavailable: tuple[str, ...]


def decode(rdram: bytes, *, sequence: int, player_pointer: int | None = None,
           profile: str = "jfg-us-retail-v1") -> Observation:
    if profile != "jfg-us-retail-v1":
        raise ObservationError("unsupported memory profile")
    if len(rdram) != RDRAM_SIZE:
        raise ObservationError("expected exactly 4 MiB big-endian RDRAM")
    if type(sequence) is not int or sequence < 0:
        raise ObservationError("invalid observation sequence")
    u32 = lambda offset: struct.unpack_from(">I", rdram, offset)[0]
    count = u32(ACTOR_COUNT)
    if count > MAX_ACTORS:
        raise ObservationError("actor count exceeds diagnostic bound")
    table = physical(u32(ACTOR_LIST), count * 4) if count else None
    actors = []
    seen = set()
    for index in range(count):
        pointer = u32(table + index * 4)
        if pointer == 0:
            continue  # empty slots are not actors
        offset = physical(pointer, 0x44)
        if offset in seen:
            raise ObservationError("duplicate/aliased actor pointer")
        seen.add(offset)
        header_pointer = u32(offset + 0x40)
        header = physical(header_pointer, 0x14)
        raw_name = rdram[header + 4:header + 0x14].split(b"\0", 1)[0]
        # Preserve unknown names without accidentally identifying an enemy.
        name = raw_name.decode("ascii", errors="backslashreplace")
        position = struct.unpack_from(">fff", rdram, offset + 0x0C)
        if not all(math.isfinite(value) for value in position):
            raise ObservationError("non-finite actor position")
        actors.append(Actor(pointer, header_pointer, name,
                            struct.unpack_from(">H", rdram, offset)[0], position))
    player = None
    if player_pointer is not None:
        wanted = physical(player_pointer, 0x44)
        player = next((actor for actor in actors
                       if physical(actor.address, 0x44) == wanted), None)
        if player is None:
            raise ObservationError("player pointer is not in current actor table")
    unavailable = ["health", "ammo", "camera", "level_id", "progression",
                   "collision", "hostility"]
    if player is None:
        unavailable.append("player")
    return Observation(1, profile, sequence, rdram[FRONT_MODE], u32(RNG),
                       tuple(actors), player, tuple(unavailable))


class FreshnessGuard:
    """Monotonic observations within a session; restores require a new guard."""

    def __init__(self) -> None:
        self.last_sequence = -1

    def accept(self, observation: Observation) -> None:
        if observation.sequence <= self.last_sequence:
            raise ObservationError("stale or reordered observation")
        self.last_sequence = observation.sequence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rdram", type=Path)
    parser.add_argument("--player", type=lambda text: int(text, 0))
    parser.add_argument("--sequence", type=int, default=0)
    args = parser.parse_args()
    result = decode(args.rdram.read_bytes(), sequence=args.sequence,
                    player_pointer=args.player)
    print(json.dumps(asdict(result), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
