"""Inspect a navigation-mod export and optionally write local OBJ/SVG files."""
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
import time


def _read(path: Path) -> dict:
    if path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("Export is too large")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != 1:
        raise ValueError("Unsupported navigation export schema")
    return value


def _point(value: object) -> list:
    if (not isinstance(value, list) or len(value) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError("Invalid map coordinate")
    return value


def load_snapshot(directory: Path, *, allow_stale: bool = False) -> tuple[dict, dict]:
    live = _read(directory / "live.json")
    mesh = _read(directory / "mesh.json")
    current = _read(directory / "live.json")
    for item in (live, mesh, current):
        if (type(item.get("level")) is not int or not 0 <= item["level"] <= 0xffffffff or
                type(item.get("generation")) is not int or item["generation"] < 1):
            raise ValueError("Invalid room identity")
    def key(item: dict) -> tuple[int, int]:
        return item["level"], item["generation"]
    if key(live) != key(mesh) or key(current) != key(mesh):
        raise ValueError("Room changed during the read; retry after loading finishes")
    live = current
    if not live.get("mesh_ready") or not isinstance(live.get("player"), dict):
        raise ValueError("No active player and map; enter gameplay first")
    if not allow_stale:
        age = time.time() * 1000 - live.get("timestamp_ms", 0)
        if not 0 <= age <= 5000:
            raise ValueError("Export is stale; the game may be closed or paused")
    vertices, triangles = mesh.get("vertices"), mesh.get("triangles")
    if not isinstance(vertices, list) or not 0 < len(vertices) <= 131072:
        raise ValueError("Invalid vertex count")
    if not isinstance(triangles, list) or not 0 < len(triangles) <= 262144:
        raise ValueError("Invalid triangle count")
    for vertex in vertices:
        _point(vertex)
    for triangle in triangles:
        indices = triangle.get("v") if isinstance(triangle, dict) else None
        if (not isinstance(indices, list) or len(indices) != 3 or
                any(type(i) is not int or not 0 <= i < len(vertices) for i in indices)):
            raise ValueError("Invalid triangle indices")
        _point(triangle.get("normal"))
    _point(live["player"].get("position"))
    if not isinstance(live.get("exits"), list):
        raise ValueError("Invalid exit list")
    for exit_data in live["exits"]:
        _point(exit_data.get("position"))
        if (type(exit_data.get("destination_code")) is not int or
                not 0 <= exit_data["destination_code"] <= 65535):
            raise ValueError("Invalid exit destination code")
    for field in ("markers", "npcs"):
        entries = live.get(field, [])
        if not isinstance(entries, list) or len(entries) > 1024:
            raise ValueError("Invalid marker list")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Invalid marker")
            _point(entry.get("position"))
            if (not isinstance(entry.get("label"), str) or
                    not 0 < len(entry["label"]) <= 80 or
                    not isinstance(entry.get("kind"), str) or len(entry["kind"]) > 32):
                raise ValueError("Invalid marker label or kind")
            if field == "npcs" and entry["kind"] not in ("npc", "tribal"):
                raise ValueError("Invalid NPC category")
    return mesh, live


def write_obj(path: Path, mesh: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as out:
        out.write("# Local ROM-derived JFG stage geometry; Y is up.\n")
        for vertex in mesh["vertices"]:
            out.write("v " + " ".join(format(v, ".9g") for v in vertex) + "\n")
        for face in mesh["triangles"]:
            out.write("f " + " ".join(str(v + 1) for v in face["v"]) + "\n")


def write_svg(path: Path, mesh: dict, live: dict) -> None:
    points = mesh["vertices"] + [live["player"]["position"]] + [e["position"] for e in live["exits"]]
    points += [e["position"] for field in ("markers", "npcs") for e in live.get(field, [])]
    xs, zs = [v[0] for v in points], [v[2] for v in points]
    left, top = min(xs), min(zs)
    scale = 940 / max(max(xs) - left, max(zs) - top, 1)
    def project(point: list) -> str:
        return f"{30 + (point[0] - left) * scale:.2f},{60 + (point[2] - top) * scale:.2f}"
    with path.open("w", encoding="utf-8", newline="\n") as out:
        out.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1040">\n')
        out.write('<rect width="1000" height="1040" fill="#101822"/>\n')
        out.write('<text x="24" y="28" fill="white" font-family="sans-serif" font-size="18">'
                  'Stage geometry · yellow exits · cyan player (not a validated route)</text>\n')
        for triangle in mesh["triangles"]:
            vertices = " ".join(project(mesh["vertices"][i]) for i in triangle["v"])
            out.write(f'<polygon points="{vertices}" fill="none" stroke="#426078" stroke-width=".6"/>\n')
        for index, exit_data in enumerate(live["exits"]):
            x, z = project(exit_data["position"]).split(",")
            label = html.escape(f'Exit {index}: 0x{exit_data["destination_code"]:04x}')
            out.write(f'<circle cx="{x}" cy="{z}" r="5" fill="#ffd45b"/>\n')
            out.write(f'<text x="{float(x)+8:.2f}" y="{z}" fill="#ffd45b" font-family="sans-serif" font-size="13">{label}</text>\n')
        colors = {"npc": "#6495ed", "tribal": "#ffffff", "weapon": "#ffa500",
                  "key": "#dda0dd", "opened": "#808080"}
        for field in ("markers", "npcs"):
            for marker in live.get(field, []):
                x, z = map(float, project(marker["position"]).split(","))
                color = colors.get(marker["kind"], "#90ee90")
                label = html.escape(marker["label"])
                if field == "npcs":
                    shape = f"{x},{z-6} {x+6},{z} {x},{z+6} {x-6},{z}"
                    out.write(f'<polygon points="{shape}" fill="{color}"/>\n')
                else:
                    out.write(f'<rect x="{x-4}" y="{z-4}" width="8" height="8" fill="{color}"/>\n')
                out.write(f'<text x="{x+8:.2f}" y="{z}" fill="{color}" font-family="sans-serif" font-size="13">{label}</text>\n')
        x, z = project(live["player"]["position"]).split(",")
        out.write(f'<circle cx="{x}" cy="{z}" r="6" fill="#50edff"/>\n</svg>\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="One run's maps directory")
    parser.add_argument("--allow-stale", action="store_true", help="Inspect a saved capture after the game exits")
    parser.add_argument("--obj", type=Path, help="Write geometry for a 3D editor")
    parser.add_argument("--svg", type=Path, help="Write a top-down preview for a browser")
    args = parser.parse_args()
    try:
        mesh, live = load_snapshot(args.directory, allow_stale=args.allow_stale)
        if args.obj:
            write_obj(args.obj, mesh)
        if args.svg:
            write_svg(args.svg, mesh, live)
        print(json.dumps({"level": live["level"], "generation": live["generation"],
                          "vertices": len(mesh["vertices"]), "triangles": len(mesh["triangles"]),
                          "player": live["player"], "exits": live["exits"],
                          "npcs": live.get("npcs", []), "items": live.get("markers", [])}, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Map export unavailable: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
