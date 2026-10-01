#!/usr/bin/env python3
"""Build the pinned JFG decomp twice in Linux and compare safe summaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from .parse_upstream_report import validate_report
    from .summarize_overlays import (
        OverlayRomLayout,
        load_private_overlay_layout,
        summarize_overlay_text,
        summarize_rom,
    )
    from .validate_elf import summarize
except ImportError:  # Direct script execution.
    from parse_upstream_report import validate_report
    from summarize_overlays import (
        OverlayRomLayout,
        load_private_overlay_layout,
        summarize_overlay_text,
        summarize_rom,
    )
    from validate_elf import summarize

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROM_SHA1 = "493ced9008dbe932d6e91179b68e8630cf23a023"
EXPECTED_DECOMP_COMMIT = "b49aa4791e8fb1e7acd3bba10346876358d0a9a7"
ENVIRONMENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,63}$")


def digest(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def run(command: list[str], cwd: Path, log_path: Path) -> None:
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"$ {' '.join(command)}\n")
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if completed.returncode != 0:
        raise RuntimeError(f"command failed; see {log_path.name}")


def current_commit(repository: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def first_line(command: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]


def capture(command: list[str], cwd: Path) -> str:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.rstrip()


def submodule_pins(repository: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    output = capture(["git", "submodule", "status", "--recursive"], repository)
    for line in output.splitlines():
        if not line or line[0] != " ":
            raise RuntimeError("upstream submodule checkout is not clean and initialized")
        parts = line[1:].split()
        if len(parts) < 2 or not re.fullmatch(r"[0-9a-f]{40}", parts[0]):
            raise RuntimeError("upstream submodule status is not parseable")
        pins[parts[1]] = parts[0]
    return dict(sorted(pins.items()))


def manifest_digest(directory: Path) -> str:
    records = [
        {
            "path": path.relative_to(directory).as_posix(),
            "size": path.stat().st_size,
            "sha256": digest(path, "sha256"),
        }
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    ]
    if not records:
        raise RuntimeError("expected tool artifact directory is empty")
    rendered = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(rendered).hexdigest()


def python_package_versions(interpreter: Path) -> dict[str, str]:
    distributions = ["splat64", "spimdisasm", "mapfile-parser", "PyYAML"]
    code = (
        "import importlib.metadata,json;"
        f"print(json.dumps({{name:importlib.metadata.version(name) for name in {distributions!r}}},"
        "sort_keys=True))"
    )
    return json.loads(first_line([str(interpreter), "-c", code]))


def tool_evidence(decomp: Path) -> dict[str, object]:
    interpreter = decomp / ".venv" / "bin" / "python3"
    objdiff = decomp / "tools" / "objdiff" / "objdiff-cli"
    n64crc = decomp / "tools" / "n64crc"
    ido = decomp / "tools" / "ido-recomp" / "linux"
    return {
        "versions": {
            "git": first_line(["git", "--version"]),
            "make": first_line(["make", "--version"]),
            "gcc": first_line(["gcc", "--version"]),
            "readelf": first_line(["readelf", "--version"]),
            "mips_as": first_line(["mips-linux-gnu-as", "--version"]),
            "mips_ld": first_line(["mips-linux-gnu-ld", "--version"]),
            "mips_objcopy": first_line(["mips-linux-gnu-objcopy", "--version"]),
            "python": platform.python_version(),
            "python_packages": python_package_versions(interpreter),
        },
        "artifacts": {
            "ido_recomp_manifest_sha256": manifest_digest(ido),
            "objdiff_cli_sha256": digest(objdiff, "sha256"),
            "n64crc_sha256": digest(n64crc, "sha256"),
        },
    }


def build_once(
    decomp: Path,
    results: Path,
    run_number: int,
    jobs: int,
    overlay_layout: OverlayRomLayout,
) -> dict[str, object]:
    log_path = results / f"build-{run_number}.log"
    run(["make", "clean"], decomp, log_path)
    run(["make", f"-j{jobs}"], decomp, log_path)

    rom = decomp / "build" / "jfg.us.z64"
    elf = decomp / "build" / "jfg.us.elf"
    linker_map = decomp / "build" / "jfg.us.map"
    if not rom.is_file() or not elf.is_file() or not linker_map.is_file():
        raise RuntimeError("upstream build did not produce the expected ROM, ELF, and map")

    rom_sha1 = digest(rom, "sha1")
    if rom_sha1 != EXPECTED_ROM_SHA1:
        raise RuntimeError("upstream build ROM does not match the supported US ROM")

    run(
        [str(decomp / ".venv" / "bin" / "python3"), "-m", "mapfile_parser",
         "objdiff_report", "--version", "us"],
        decomp,
        log_path,
    )
    report = decomp / "build" / "report.json"
    splat_layout = decomp / "ver" / "splat" / "jfg.us.yaml"
    return {
        "run": run_number,
        "rom_sha1": rom_sha1,
        "elf": summarize(elf, linker_map),
        "report": validate_report(report),
        "overlays": {
            "rom_table": summarize_rom(rom, overlay_layout),
            "splat_layout": summarize_overlay_text(
                splat_layout.read_text(encoding="utf-8")
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument(
        "--overlay-layout",
        required=True,
        type=Path,
        help="private JSON layout outside the repository or in a Git-ignored path",
    )
    parser.add_argument(
        "--decomp",
        type=Path,
        default=ROOT / "tools" / "upstream" / "Jet-Force-Gemini",
    )
    parser.add_argument(
        "--environment-id",
        required=True,
        help="Privacy-safe label such as ubuntu-24.04 (lowercase letters, digits, dot, dash)",
    )
    parser.add_argument("--jobs", type=int, default=max(1, min(os.cpu_count() or 1, 8)))
    arguments = parser.parse_args()

    if sys.platform != "linux":
        print(
            "Phase 1 requires Linux. On Windows, initialize WSL2/Ubuntu and run "
            "this script from that environment.",
            file=sys.stderr,
        )
        return 2
    if not ENVIRONMENT_ID_RE.fullmatch(arguments.environment_id):
        print("Invalid --environment-id.", file=sys.stderr)
        return 2

    rom = arguments.rom.resolve()
    decomp = arguments.decomp.resolve()
    if not rom.is_file() or digest(rom, "sha1") != EXPECTED_ROM_SHA1:
        print("The supplied ROM is missing or has the wrong SHA-1.", file=sys.stderr)
        return 2
    if not (decomp / ".git").exists():
        print("Pinned JFG decomp clone is missing under tools/upstream.", file=sys.stderr)
        return 2
    if current_commit(decomp) != EXPECTED_DECOMP_COMMIT:
        print("JFG decomp checkout does not match the required pin.", file=sys.stderr)
        return 2
    try:
        overlay_layout = load_private_overlay_layout(arguments.overlay_layout)
    except ValueError as error:
        print(f"Private overlay layout is invalid: {error}", file=sys.stderr)
        return 2

    results_root = ROOT / "tools" / "results" / "phase1"
    results = results_root / arguments.environment_id
    if results.exists():
        shutil.rmtree(results)
    results.mkdir(parents=True, exist_ok=True)
    log_path = results / "setup.log"

    try:
        run(["git", "diff", "--quiet"], decomp, log_path)
        run(["git", "diff", "--cached", "--quiet"], decomp, log_path)
        if capture(["git", "ls-files", "--others", "--exclude-standard"], decomp):
            raise RuntimeError("upstream checkout has non-ignored untracked files")
        run(["git", "config", "core.autocrlf", "false"], decomp, log_path)
        run(["git", "checkout-index", "--all", "--force"], decomp, log_path)
        run(["git", "submodule", "update", "--init", "--recursive"], decomp, log_path)
        run(
            [
                "git",
                "submodule",
                "foreach",
                "--recursive",
                (
                    "git diff --quiet && git diff --cached --quiet && "
                    "test -z \"$(git ls-files --others --exclude-standard)\""
                ),
            ],
            decomp,
            log_path,
        )
        run(
            [
                "git",
                "submodule",
                "foreach",
                "--recursive",
                "git config core.autocrlf false && git checkout-index --all --force",
            ],
            decomp,
            log_path,
        )
        destination = decomp / "baseroms" / "baserom.us.z64"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(rom, destination)
        environment = decomp / ".venv"
        if environment.exists():
            shutil.rmtree(environment)
        run(["make", "distclean"], decomp, log_path)
        run(["make", "setup"], decomp, log_path)
        run(["make", "extract"], decomp, log_path)
        source = {
            "decomp_tree": capture(["git", "rev-parse", "HEAD^{tree}"], decomp),
            "submodules": submodule_pins(decomp),
            "requirements_sha256": digest(decomp / "requirements.txt", "sha256"),
        }
        tools = tool_evidence(decomp)
        first = build_once(decomp, results, 1, arguments.jobs, overlay_layout)
        second = build_once(decomp, results, 2, arguments.jobs, overlay_layout)
    except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError) as error:
        print(f"Phase 1 build failed: {error}", file=sys.stderr)
        return 1

    comparable_first = {key: value for key, value in first.items() if key != "run"}
    comparable_second = {key: value for key, value in second.items() if key != "run"}
    equivalent = comparable_first == comparable_second
    evidence = {
        "schema_version": 1,
        "environment_id": arguments.environment_id,
        "environment": {
            "distribution": platform.freedesktop_os_release().get("PRETTY_NAME", "unknown"),
        },
        "source": source,
        "tools": tools,
        "decomp_commit": EXPECTED_DECOMP_COMMIT,
        "input_rom_sha1": EXPECTED_ROM_SHA1,
        "builds_equivalent": equivalent,
        "runs": [first, second],
    }
    (results / "build-evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not equivalent:
        print("The two clean upstream builds were not equivalent.", file=sys.stderr)
        return 1
    print("Two clean upstream builds produced equivalent ROM and ELF summaries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
