#!/usr/bin/env python3
"""Report whether the Phase 1 and Phase 2 development prerequisites are ready."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

try:
    from .summarize_overlays import load_private_overlay_layout
except ImportError:  # Direct script execution.
    from summarize_overlays import load_private_overlay_layout

ROOT = Path(__file__).resolve().parents[1]
PHASE1_WSL_DISTRIBUTIONS = ("Ubuntu-22.04", "Ubuntu-24.04")
VENV_PROBE = (
    "import tempfile,venv;"
    "directory=tempfile.TemporaryDirectory();"
    "venv.EnvBuilder(with_pip=True).create(directory.name);"
    "directory.cleanup()"
)
PHASE1_LINUX_PROBES = (
    ("Git", ("git", "--version")),
    ("GNU Make", ("make", "--version")),
    ("GCC", ("gcc", "--version")),
    ("pkg-config", ("pkg-config", "--version")),
    ("wget", ("wget", "--version")),
    ("readelf", ("readelf", "--version")),
    ("MIPS assembler", ("mips-linux-gnu-as", "--version")),
    ("MIPS linker", ("mips-linux-gnu-ld", "--version")),
    ("MIPS objcopy", ("mips-linux-gnu-objcopy", "--version")),
    ("Python venv with pip", ("python3", "-c", VENV_PROBE)),
)

CommandRunner = Callable[[list[str]], bool]


def locate_cmake() -> Path | None:
    discovered = shutil.which("cmake")
    if discovered:
        return Path(discovered)
    if sys.platform == "win32":
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        candidate = (
            program_files
            / "Microsoft Visual Studio"
            / "2022"
            / "Community"
            / "Common7"
            / "IDE"
            / "CommonExtensions"
            / "Microsoft"
            / "CMake"
            / "CMake"
            / "bin"
            / "cmake.exe"
        )
        if candidate.is_file():
            return candidate
    return None


def command_ok(command: list[str]) -> bool:
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=20)
        return True
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def phase1_linux_dependency_failures(
    scope: str,
    *,
    prefix: tuple[str, ...] = (),
    runner: CommandRunner | None = None,
) -> list[str]:
    """Return actionable failures for the upstream Linux build toolchain."""
    check = runner or command_ok
    failures: list[str] = []
    for label, command in PHASE1_LINUX_PROBES:
        if not check([*prefix, *command]):
            failures.append(f"{scope}: {label} is missing or unusable")
    return failures


def windows_phase1_dependency_failures(
    *, runner: CommandRunner | None = None
) -> list[str]:
    """Verify WSL itself and both clean Phase 1 Ubuntu environments."""
    check = runner or command_ok
    if not check(["wsl", "--status"]):
        return ["WSL2 is not enabled or ready"]

    failures: list[str] = []
    for distribution in PHASE1_WSL_DISTRIBUTIONS:
        prefix = ("wsl", "--distribution", distribution, "--exec")
        if not check([*prefix, "sh", "-lc", "true"]):
            failures.append(
                f"{distribution}: required WSL distribution is missing or unusable"
            )
            continue
        failures.extend(
            phase1_linux_dependency_failures(
                distribution,
                prefix=prefix,
                runner=check,
            )
        )
    return failures


def verify_tool_pins() -> list[str]:
    errors: list[str] = []
    lock = json.loads((ROOT / "dependencies.lock.json").read_text(encoding="utf-8"))
    upstream = ROOT / "tools" / "upstream"
    for repository in lock["repositories"]:
        if repository["use"] == "excluded-pending-permission":
            continue
        path = upstream / {
            "jfg-decomp": "Jet-Force-Gemini",
            "n64recomp": "N64Recomp",
            "n64modernruntime": "N64ModernRuntime",
            "rt64": "rt64",
        }.get(repository["id"], repository["id"])
        if not (path / ".git").exists():
            errors.append(f"{repository['id']}: clone is missing under tools/upstream")
            continue
        actual = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if actual != repository["commit"]:
            errors.append(f"{repository['id']}: checkout does not match dependencies.lock.json")
            continue
        for submodule, expected in repository["recursive_submodules"].items():
            tree = subprocess.run(
                ["git", "-C", str(path), "ls-tree", "HEAD", "--", submodule],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            fields = tree.split()
            actual_submodule = fields[2] if len(fields) >= 3 else ""
            if actual_submodule != expected:
                errors.append(
                    f"{repository['id']}:{submodule}: gitlink pin does not match lock"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase1", action="store_true", help="require a usable WSL/Linux builder")
    parser.add_argument(
        "--overlay-layout",
        type=Path,
        help="private Phase 1 overlay layout outside the repository or Git-ignored",
    )
    arguments = parser.parse_args()

    failures: list[str] = []
    print(f"Python: {'ready' if sys.version_info >= (3, 11) else 'too old'}")
    if sys.version_info < (3, 11):
        failures.append("Python 3.11 or newer is required")

    cmake = locate_cmake()
    print(f"CMake: {'ready' if cmake else 'missing'}")
    if not cmake:
        failures.append("CMake 3.20 or newer is required")

    print(f"Git: {'ready' if shutil.which('git') else 'missing'}")
    if not shutil.which("git"):
        failures.append("Git is required")

    failures.extend(verify_tool_pins())

    if arguments.phase1:
        if arguments.overlay_layout is None:
            phase1_failures = ["Phase 1 requires a private --overlay-layout file"]
        else:
            try:
                load_private_overlay_layout(arguments.overlay_layout)
            except ValueError as error:
                phase1_failures = [f"Private overlay layout is invalid: {error}"]
            else:
                phase1_failures = []
        if sys.platform == "win32":
            toolchain_failures = windows_phase1_dependency_failures()
            print(f"WSL/Linux: {'ready' if not toolchain_failures else 'not ready'}")
        elif sys.platform.startswith("linux"):
            toolchain_failures = phase1_linux_dependency_failures("Linux")
            print(
                f"Phase 1 Linux toolchain: "
                f"{'ready' if not toolchain_failures else 'not ready'}"
            )
        else:
            toolchain_failures = [
                "Phase 1 requires Linux or Windows with the required WSL2 distributions"
            ]
            print("Phase 1 Linux toolchain: unsupported host")
        phase1_failures.extend(toolchain_failures)
        failures.extend(phase1_failures)

    if failures:
        print("Doctor found blockers:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Doctor passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
