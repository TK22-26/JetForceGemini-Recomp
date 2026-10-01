"""Propose a terrain-sampled route; only subsequent ordinary-input tests prove traversal."""
import argparse
import heapq
import json
import math
from pathlib import Path

from scripts.phase95_terrain import terrain, vertical_surfaces
from scripts.phase95_observation import ObservationError


def propose(geometry, start, target, *, spacing=40, margin=1200, radius=95, max_nodes=10000):
    if any(len(point) != 3 or not all(math.isfinite(v) for v in point) for point in (start, target)):
        raise ValueError("invalid route endpoints")
    if not 10 <= spacing <= 100 or not 100 <= margin <= 2000 or not 1 <= radius <= 100:
        raise ValueError("invalid surface sampling bounds")
    if not 1 <= max_nodes <= 20000:
        raise ValueError("invalid surface search budget")
    cache = {}

    def heights(i, j):
        key = (i, j)
        if key not in cache:
            x, z = start[0] + i * spacing, start[2] + j * spacing
            cache[key] = sorted(set(round(hit["height"], 4) for hit in vertical_surfaces(geometry, x, z)))
        return cache[key]

    roots = heights(0, 0)
    if not roots:
        raise ObservationError("no sampled surface under route start")
    root = (0, 0, min(roots, key=lambda y: abs(y - start[1])))
    if abs(root[2] - start[1]) > 40:
        raise ObservationError("start surface too far from player")

    def position(key):
        return (start[0] + key[0] * spacing, key[2], start[2] + key[1] * spacing)

    def heuristic(key):
        return math.dist(position(key), target)

    low_x, high_x = min(start[0], target[0]) - margin, max(start[0], target[0]) + margin
    low_z, high_z = min(start[2], target[2]) - margin, max(start[2], target[2]) + margin
    costs, parents = {root: 0.0}, {root: None}
    queue = [(heuristic(root), 0.0, root)]
    expanded = 0
    while queue and expanded < max_nodes:
        _, cost, current = heapq.heappop(queue)
        if cost != costs[current]:
            continue
        expanded += 1
        if heuristic(current) <= radius:
            route = []
            while current is not None:
                route.append(position(current))
                current = parents[current]
            return {"kind": "jfg-phase95-surface-proposal", "acceptance": False,
                    "waypoints": route[::-1], "expanded": expanded, "spacing": spacing,
                    "radius": radius, "target": target, "margin": margin,
                    "limitations": "unverified: no player clearance, material masks, dynamic doors, or jump rules"}
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            i, j = current[0] + di, current[1] + dj
            x, z = start[0] + i * spacing, start[2] + j * spacing
            if not (low_x <= x <= high_x and low_z <= z <= high_z):
                continue
            for height in heights(i, j):
                if abs(height - current[2]) > spacing * 0.75:
                    continue
                # A downward edge cannot walk through an overlapping upper
                # surface that continues at approximately the current height.
                # Such edges previously switched to a lower triangle under
                # the player's feet and produced false waypoint-layer plans.
                if (height < current[2] - 5 and
                        any(other > height + 10 and abs(other - current[2]) <= 10
                            for other in heights(i, j))):
                    continue
                # Require surface support halfway along the edge too. This is
                # still sampling, not exact swept-volume collision validation.
                previous = position(current)
                middle = vertical_surfaces(geometry, (x + previous[0]) / 2, (z + previous[2]) / 2)
                if not any(abs(hit["height"] - (height + current[2]) / 2) <= 10 for hit in middle):
                    continue
                child = (i, j, height)
                candidate = cost + math.dist(previous, position(child))
                if candidate >= costs.get(child, math.inf):
                    continue
                costs[child], parents[child] = candidate, current
                heapq.heappush(queue, (candidate + heuristic(child), candidate, child))
    raise ObservationError(f"surface proposal incomplete after {expanded} expansions; not proof of unreachable target")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rdram", type=Path)
    parser.add_argument("--start", type=float, nargs=3, required=True)
    parser.add_argument("--target", type=float, nargs=3, required=True)
    args = parser.parse_args()
    print(json.dumps(propose(terrain(args.rdram.read_bytes()), args.start, args.target), indent=2))


if __name__ == "__main__":
    main()
