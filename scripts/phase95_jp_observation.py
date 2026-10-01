"""Conservative read-only observations from Japanese TAS RDRAM snapshots.

The actor layout is supported by multiple extracted JP states. Mode, level,
and RNG offsets additionally require exact resident-code signatures.
This module does not authorize controller actions or establish US/native parity.
Only entries inside the declared actor count are current; heap data beyond it
can contain valid-looking stale actor pointers and names.
"""

from dataclasses import asdict, dataclass
import argparse
import json
import math
from pathlib import Path
import struct


RDRAM_SIZE = 0x800000
ACTOR_LIST = 0xF2BB4
ACTOR_COUNT = 0xF2BB8
CANDIDATE_PLAYER_POINTER = 0xF8824
FRONT_MODE = 0xA50C0
LEVEL_WORD = 0xFB024
RNG_SEED = 0xA32E4
MAX_ACTORS = 1024
PROFILE = "jfg-jp-tas-observed-v1"
UNVERIFIED_FIELDS = ("progression", "health", "ammo", "collision", "hostility")

# JP resident getter and mathSeed/mathRnd bytes observed unchanged in six
# extracted states, including a zero-actor transition. The RNG address also
# appears as rngSeed in the upstream JP symbol map. This is not a US offset
# translation rule; each address below has independent JP code evidence.
CODE_SIGNATURES = (
    (0x588B4, bytes.fromhex("3C02800A904250C003E0000800000000")),
    (0x445BC, bytes.fromhex("3C0280108C42B02403E0000800000000")),
    (0x48C50, bytes.fromhex("3C01800A03E00008AC2432E4")),
    (0x48C68, bytes.fromhex("3C08800A8D0832E4")),
    (0x48CA0, bytes.fromhex("01694026AC2832E4")),
)


class JPObservationError(ValueError):
    """The snapshot cannot safely support this narrow JP observation."""


def _physical(pointer, size):
    # Only the KSEG0 pointer class seen in all three validated snapshots is
    # accepted. Do not silently decode arbitrary host or ROM pointers.
    if (type(pointer) is not int or type(size) is not int or size <= 0 or
            not 0x80000000 <= pointer < 0x80800000):
        raise JPObservationError(f"unsupported JP RDRAM pointer: {pointer!r}")
    offset = pointer - 0x80000000
    if offset % 4 or offset + size > RDRAM_SIZE:
        raise JPObservationError("unaligned or out-of-range JP RDRAM span")
    return offset


@dataclass(frozen=True)
class JPActor:
    address: int
    header: int
    name: str
    yaw: int
    position: tuple[float, float, float]


@dataclass(frozen=True)
class JPObservation:
    schema: int
    profile: str
    acceptance: bool
    frame: int
    actor_table: int | None
    actor_count: int
    candidate_player_pointer: int
    actors: tuple[JPActor, ...]
    player: JPActor | None
    player_resolution: str
    front_mode: int
    rng: int
    level_id: int
    progression: None
    unverified_fields: tuple[str, ...]


def decode(rdram: bytes, *, frame: int) -> JPObservation:
    """Decode the JP actor table; never infer level/progression from US offsets."""
    if len(rdram) != RDRAM_SIZE:
        raise JPObservationError("expected exactly 8 MiB logical JP RDRAM")
    if type(frame) is not int or frame < 0:
        raise JPObservationError("invalid frame")
    for offset, signature in CODE_SIGNATURES:
        if rdram[offset:offset + len(signature)] != signature:
            raise JPObservationError(f"JP resident code profile mismatch at {offset:#x}")

    def u32(offset):
        return struct.unpack_from(">I", rdram, offset)[0]

    count = u32(ACTOR_COUNT)
    if count > MAX_ACTORS:
        raise JPObservationError("JP actor count exceeds diagnostic bound")
    table_pointer = u32(ACTOR_LIST)
    table = _physical(table_pointer, max(count, 1) * 4) if count or table_pointer else None
    actors = []
    seen = set()
    for index in range(count):
        pointer = u32(table + index * 4)
        offset = _physical(pointer, 0x44)
        if offset in seen:
            raise JPObservationError("duplicate JP actor pointer")
        seen.add(offset)
        header_pointer = u32(offset + 0x40)
        header = _physical(header_pointer, 0x14)
        name_bytes = rdram[header + 4:header + 0x14]
        if b"\0" not in name_bytes:
            raise JPObservationError("unterminated JP actor name")
        raw_name = name_bytes.split(b"\0", 1)[0]
        if not raw_name or any(byte < 32 or byte > 126 for byte in raw_name):
            raise JPObservationError("invalid JP actor name")
        name = raw_name.decode("ascii")
        position = struct.unpack_from(">fff", rdram, offset + 0x0C)
        if not all(math.isfinite(value) for value in position):
            raise JPObservationError("non-finite JP actor position")
        actors.append(JPActor(pointer, header_pointer, name,
                              struct.unpack_from(">H", rdram, offset)[0],
                              position))

    candidate = u32(CANDIDATE_PLAYER_POINTER)
    named_players = [actor for actor in actors if actor.name == "playerBoy"]
    if not named_players:
        player = None
        resolution = "no_named_player"
    elif len(named_players) != 1:
        player = None
        resolution = "multiple_named_players"
    elif named_players[0].address != candidate:
        # A cutscene may leave a named actor in the current table after the
        # candidate global stops identifying it. Preserve valid table facts.
        player = None
        resolution = "candidate_mismatch"
    else:
        player = named_players[0]
        resolution = "matched"
    return JPObservation(1, PROFILE, False, frame, table_pointer if table is not None else None,
                         count, candidate, tuple(actors), player, resolution,
                         rdram[FRONT_MODE], u32(RNG_SEED),
                         struct.unpack_from(">i", rdram, LEVEL_WORD)[0], None,
                         UNVERIFIED_FIELDS + (() if player is not None else ("player",)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rdram", type=Path)
    parser.add_argument("--frame", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(asdict(decode(args.rdram.read_bytes(), frame=args.frame)),
                     sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
