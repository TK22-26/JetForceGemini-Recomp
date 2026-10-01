"""Build private, gap-explicit inputs for the existing cold-boot gameplay probe."""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.build_phase9_route_replays import (
    COLD_BOOT_GAMEPLAY_END, Event, cold_boot_to_gameplay_probe_route, write_replay,
)


def explicit_neutral_gaps(events: list[Event], end: int) -> list[Event]:
    result = []
    cursor = 0
    for event in events:
        if event.first < cursor or event.last <= event.first or event.last > end:
            raise ValueError("invalid scripted route interval")
        if event.first > cursor:
            result.append(Event(cursor, event.first, 1, 0, 0, 0))
        result.append(event)
        cursor = event.last
    if cursor < end:
        result.append(Event(cursor, end, 1, 0, 0, 0))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--initial-pak", type=Path, required=True)
    args = parser.parse_args()
    pak = args.initial_pak.read_bytes()
    route = explicit_neutral_gaps(cold_boot_to_gameplay_probe_route(),
                                  COLD_BOOT_GAMEPLAY_END)
    args.output.mkdir(parents=True, exist_ok=False)
    write_replay(args.output / "controller.input", route)
    flash = b"\xff" * 0x20000
    (args.output / "initial.flash").write_bytes(flash)
    (args.output / "initial.pak").write_bytes(pak)
    digest = lambda value: hashlib.sha256(value).hexdigest()
    manifest = {"kind": "jfg-phase9-cold-boot-probe", "schema": 1,
                "acceptance": False, "target_retrace": COLD_BOOT_GAMEPLAY_END,
                "input_sha256": digest((args.output / "controller.input").read_bytes()),
                "flash_sha256": digest(flash), "pak_sha256": digest(pak),
                "input_gaps": "explicit-connected-neutral"}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
