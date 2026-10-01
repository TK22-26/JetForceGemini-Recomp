"""Read-only registered collision-model bounds; excludes undecoded static terrain."""
import argparse
import json
import math
from pathlib import Path
import struct

from scripts.phase95_observation import decode, physical, ObservationError


def bounds_inventory(memory, sequence=0):
    state = decode(memory, sequence=sequence)
    if state.front_mode != 16:
        raise ObservationError("collision inventory requires gameplay")
    # Pin the actual resident accessor instructions, not just an upstream label.
    expected = (0x3C0E8010, 0x8DCE47E0, 0x3C028010, 0xAC8E0000,
                0x8C4247E4, 0x03E00008, 0)
    if struct.unpack_from(">7I", memory, 0x7E484) != expected:
        raise ObservationError("hitGetHitModels instructions do not match profile")
    count, pointer = struct.unpack_from(">iI", memory, 0x1047E0)
    if not 0 <= count <= 1024:
        raise ObservationError("invalid collision model count")
    table = physical(pointer, count * 4) if count else None
    actors = {physical(actor.address, 0x60): actor for actor in state.actors}
    result, seen = [], set()
    for index in range(count):
        address = struct.unpack_from(">I", memory, table + index * 4)[0]
        offset = physical(address, 0x60)
        if offset not in actors or offset in seen:
            raise ObservationError("collision entry is stale or duplicated")
        seen.add(offset)
        actor = actors[offset]
        collision = physical(struct.unpack_from(">I", memory, offset + 0x5C)[0], 0x118)
        lower = struct.unpack_from(">3f", memory, collision + 0x100)
        upper = struct.unpack_from(">3f", memory, collision + 0x10C)
        if not all(math.isfinite(v) for v in (*lower, *upper)) or any(a > b for a, b in zip(lower, upper)):
            raise ObservationError("invalid collision bounds")
        properties = physical(struct.unpack_from(">I", memory, offset + 0x4C)[0], 0xC)
        result.append({"actor": address, "name": actor.name, "lower": lower, "upper": upper,
                       "polylist_enabled": bool(struct.unpack_from(">H", memory, properties + 0xA)[0] & 1)})
    return {"kind": "jfg-phase95-collision-bounds", "acceptance": False, "models": result,
            "limitations": "registered object bounds only; not static terrain, exact polygons, or traversability"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rdram", type=Path)
    args = parser.parse_args()
    print(json.dumps(bounds_inventory(args.rdram.read_bytes()), indent=2))


if __name__ == "__main__":
    main()
