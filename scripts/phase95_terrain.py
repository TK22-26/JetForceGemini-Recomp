"""Read-only track geometry inventory. Render batches are not a walkability mask."""
import argparse
import json
import math
from pathlib import Path
import struct

from scripts.phase95_observation import physical, ObservationError, RDRAM_SIZE


def terrain(memory):
    if len(memory) != RDRAM_SIZE:
        raise ObservationError("terrain requires complete RDRAM")
    if struct.unpack_from(">4I", memory, 0x1B650) != (0x3C02800A, 0x8C420D60, 0x03E00008, 0):
        raise ObservationError("track accessor profile mismatch")
    u32 = lambda offset: struct.unpack_from(">I", memory, offset)[0]
    header = physical(u32(0xA0D60), 0x1C)
    count = struct.unpack_from(">h", memory, header + 0x1A)[0]
    if not 1 <= count <= 1024:
        raise ObservationError("invalid track block count")
    blocks = physical(u32(header + 4), count * 0x48)
    bounds = physical(u32(header + 8), count * 12)
    result = []
    total_triangles = 0
    for index in range(count):
        block = blocks + index * 0x48
        box = struct.unpack_from(">6h", memory, bounds + index * 12)
        if any(a > b for a, b in zip(box[:3], box[3:])):
            raise ObservationError("inverted track block bounds")
        batches = struct.unpack_from(">h", memory, block + 0x28)[0]
        if not 0 <= batches <= 4096:
            raise ObservationError("invalid track batch count")
        triangles = []
        if batches:
            groups = physical(u32(block + 0xC), (batches + 1) * 16)
            for batch in range(batches):
                group = groups + batch * 16
                base, first = struct.unpack_from(">2h", memory, group + 6)
                end = struct.unpack_from(">h", memory, group + 0x18)[0]
                flags = u32(group + 0xC)
                if base < 0 or not 0 <= first <= end <= 32768:
                    raise ObservationError("invalid track triangle range")
                total_triangles += end - first
                if total_triangles > 65536:
                    raise ObservationError("track triangle budget exceeded")
                for triangle in range(first, end):
                    face = physical(u32(block + 4) + triangle * 16, 16)
                    vertices = []
                    for local in memory[face + 1:face + 4]:
                        vertex = physical(u32(block) + (base + local) * 10, 10, aligned=False)
                        vertices.append(struct.unpack_from(">3h", memory, vertex))
                    triangles.append({"index": triangle, "batch": batch,
                                      "batch_flags": flags, "vertices": vertices})
        result.append({"index": index, "lower": box[:3], "upper": box[3:], "triangles": triangles})
    return {"kind": "jfg-phase95-track-geometry", "acceptance": False, "blocks": result,
            "limitations": "geometry only; collision masks, dynamic objects and traversal rules not applied"}


def vertical_surfaces(geometry, x, z):
    if not all(math.isfinite(v) for v in (x, z)):
        raise ValueError("invalid probe position")
    hits = []
    for block in geometry["blocks"]:
        for face in block["triangles"]:
            a, b, c = face["vertices"]
            denominator = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
            if abs(denominator) < 1e-9:
                continue
            u = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / denominator
            v = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / denominator
            w = 1 - u - v
            if min(u, v, w) >= -1e-9:
                hits.append({"block": block["index"], "triangle": face["index"],
                             "height": u * a[1] + v * b[1] + w * c[1],
                             "batch_flags": face["batch_flags"]})
    return hits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rdram", type=Path)
    parser.add_argument("--probe", nargs=2, type=float, action="append", default=[])
    args = parser.parse_args()
    result = terrain(args.rdram.read_bytes())
    print(json.dumps({"kind": result["kind"], "acceptance": False,
        "blocks": [{"index": block["index"], "lower": block["lower"], "upper": block["upper"],
                    "triangles": len(block["triangles"])} for block in result["blocks"]],
        "limitations": result["limitations"],
        "probes": [{"xz": point, "surfaces": vertical_surfaces(result, *point)}
                   for point in args.probe]}, indent=2))


if __name__ == "__main__":
    main()
