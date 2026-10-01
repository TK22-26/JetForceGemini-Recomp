"""Navigate to one declared waypoint from an isolated reference checkpoint."""
import argparse
from pathlib import Path

from scripts.phase95_bridge import Worker
from scripts.phase95_navigation import navigate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--target", type=float, nargs=3, required=True)
    parser.add_argument("--radius", type=float, default=25)
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--jump", action="store_true")
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    args = parser.parse_args()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        navigate(worker, "surface-waypoint", waypoint=args.target,
                 radius=args.radius, max_steps=args.max_steps,
                 precision=True, jump=args.jump)


if __name__ == "__main__":
    main()
