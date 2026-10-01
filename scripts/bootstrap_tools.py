#!/usr/bin/env python3
"""Clone or verify pinned upstream repositories under the ignored tools tree."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME_MAP = {
    "jfg-decomp": "Jet-Force-Gemini",
    "n64recomp": "N64Recomp",
    "n64modernruntime": "N64ModernRuntime",
    "rt64": "rt64",
    "recompfrontend": "RecompFrontend",
}


def run(arguments: list[str], cwd: Path | None = None) -> None:
    subprocess.run(arguments, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-unlicensed",
        action="store_true",
        help="also clone dependencies excluded pending permission",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="ID",
        help="restrict to the named repository id(s) from dependencies.lock.json",
    )
    arguments = parser.parse_args()

    lock = json.loads((ROOT / "dependencies.lock.json").read_text(encoding="utf-8"))
    destination_root = ROOT / "tools" / "upstream"
    destination_root.mkdir(parents=True, exist_ok=True)

    known = {repository["id"] for repository in lock["repositories"]}
    unknown = sorted(set(arguments.only) - known)
    if unknown:
        parser.error(f"unknown repository id(s): {', '.join(unknown)}")

    for repository in lock["repositories"]:
        if arguments.only and repository["id"] not in arguments.only:
            continue
        if (
            repository["use"] == "excluded-pending-permission"
            and not arguments.include_unlicensed
        ):
            print(f"Skipping {repository['id']} (permission unresolved)")
            continue
        destination = destination_root / NAME_MAP[repository["id"]]
        if not (destination / ".git").exists():
            run(["git", "clone", "--no-checkout", repository["url"], str(destination)])
        run(["git", "fetch", "--tags", "--prune", "origin"], cwd=destination)
        run(["git", "checkout", "--detach", repository["commit"]], cwd=destination)
        run(["git", "submodule", "update", "--init", "--recursive"], cwd=destination)
        print(f"Ready: {repository['id']} @ {repository['commit'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
