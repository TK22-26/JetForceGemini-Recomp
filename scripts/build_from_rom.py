#!/usr/bin/env python3
"""Experimental Windows ROM-to-native build. All generated files stay local."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ROM_SHA1 = "493ced9008dbe932d6e91179b68e8630cf23a023"
NAMES = {"jfg-decomp": "Jet-Force-Gemini", "n64recomp": "N64Recomp",
         "n64modernruntime": "N64ModernRuntime", "rt64": "rt64"}


def validate_rom(path: Path) -> str:
    if not path.is_file() or path.stat().st_size != 32 * 1024 * 1024:
        raise ValueError("Select the supported 32 MiB US big-endian .z64 ROM.")
    digest = hashlib.sha1(path.read_bytes()).hexdigest()
    if digest != ROM_SHA1:
        raise ValueError("ROM checksum does not match the supported US revision.")
    return digest


def wsl_path(path: Path) -> str:
    # This prototype supports local drive paths only; no shell interpolation.
    path = path.resolve()
    if len(path.drive) != 2 or path.drive[1] != ":":
        raise ValueError("Use a local Windows drive, not a network share.")
    return "/mnt/" + path.drive[0].lower() + path.as_posix()[2:]


def find_cmake() -> str:
    found = shutil.which("cmake")
    if found:
        return found
    base = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
    vswhere = base / "Microsoft Visual Studio/Installer/vswhere.exe"
    if vswhere.is_file():
        found = subprocess.check_output([str(vswhere), "-latest", "-products", "*",
            "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-find", "Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"],
            text=True).strip().splitlines()
        if found:
            return found[0]
    raise ValueError("Install Visual Studio 2022 C++ desktop tools with CMake support.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--distro", default="Ubuntu-24.04")
    parser.add_argument("--jobs", type=int, default=min(os.cpu_count() or 4, 8))
    parser.add_argument("--dependency-root", type=Path,
                        help="Optional existing pinned upstream source/tool cache")
    parser.add_argument("--play", action="store_true")
    parser.add_argument("--resume-native", type=Path,
                        help="Resume compilation in a local build whose ROM generation completed")
    parser.add_argument("--generation-timeout", type=int, default=3600,
                        help="Hard limit for the Linux subprocess group, in seconds")
    args = parser.parse_args()
    if os.name != "nt" or sys.version_info < (3, 11):
        parser.error("This prototype requires Windows x64 and Python 3.11 or newer.")
    if not 1 <= args.jobs <= 32:
        parser.error("--jobs must be between 1 and 32")
    if not 1 <= args.generation_timeout <= 7200:
        parser.error("--generation-timeout must be between 1 and 7200")
    rom = args.rom.resolve()
    validate_rom(rom)  # Reject before downloads or build output.
    cmake = find_cmake()
    for tool in ("git", "wsl"):
        if not shutil.which(tool):
            raise ValueError(f"Required tool missing: {tool}")
    deps = (args.dependency_root or ROOT / "tools/upstream").resolve()
    if args.resume_native:
        workspace = args.resume_native.resolve()
        if not workspace.is_relative_to((ROOT / "tools/private/local-builds").resolve()):
            raise ValueError("Resume requires a local workspace under tools/private/local-builds.")
        generation = json.loads((workspace / "generation.json").read_text())
        expected = {"normalized/sources.json", "libultra.json", "audio/production-audio-adapter.cpp",
                    "audio/brokered-rsp.hpp", "audio/brokered-jfg-audio-probe.cpp", "audio/jfg-audio-probe.cpp"}
        if generation.get("complete") is not True or generation.get("rom_sha1") != ROM_SHA1 or set(generation.get("files", {})) != expected:
            raise ValueError("ROM generation is incomplete; start a new build.")
        for name, digest in generation["files"].items():
            if hashlib.sha256((workspace / name).read_bytes()).hexdigest() != digest:
                raise ValueError("Generated build input changed; start a new build.")
    else:
        workspace = ROOT / "tools/private/local-builds" / time.strftime("%Y%m%d-%H%M%S")
        workspace.mkdir(parents=True, exist_ok=False)
    status_file = workspace / "status.json"
    records: list[dict] = (json.loads(status_file.read_text()).get("steps", [])
                           if args.resume_native and status_file.is_file() else [])
    status_file.write_text(json.dumps({"complete": False, "steps": records}, indent=2) + "\n")

    def run(name: str, command: list[str], cwd: Path = ROOT) -> None:
        print(name, flush=True)
        started = time.monotonic()
        log = workspace / (name + ".log")
        if log.exists():
            attempt = 1
            while (workspace / f"{name}.{attempt}.log").exists():
                attempt += 1
            log.rename(workspace / f"{name}.{attempt}.log")
        with log.open("w", encoding="utf-8", buffering=1) as stream:
            with subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, errors="replace") as process:
                for line in process.stdout:
                    stream.write(line)
                    if name == "generate" and re.fullmatch(r"[a-z][a-z-]+\n?", line):
                        print("  " + line.strip(), flush=True)
                code = process.wait()
        records.append({"step": name, "exit_code": code,
                        "seconds": round(time.monotonic() - started, 3)})
        (workspace / "status.json").write_text(json.dumps(
            {"complete": False, "steps": records}, indent=2) + "\n")
        if code:
            raise RuntimeError(f"{name} failed. Local diagnostic log: {log}")

    # The public lock file supplies repository URLs and immutable revisions.
    lock = json.loads((ROOT / "dependencies.lock.json").read_text())
    if not args.dependency_root:
        for entry in lock["repositories"]:
            if entry["id"] not in NAMES:
                continue
            dest = deps / NAMES[entry["id"]]
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                run("clone-" + entry["id"], ["git", "clone", "--config", "core.autocrlf=false", "--no-checkout", entry["url"], str(dest)])
                run("pin-" + entry["id"], ["git", "-C", str(dest), "checkout", "--detach", entry["commit"]])
                run("submodules-" + entry["id"], ["git", "-c", "core.autocrlf=false", "-C", str(dest), "submodule", "update", "--init", "--recursive"])
    for entry in lock["repositories"]:
        if entry["id"] in NAMES:
            dest = deps / NAMES[entry["id"]]
            head = subprocess.check_output(["git", "-C", str(dest), "rev-parse", "HEAD"], text=True).strip()
            if head != entry["commit"]:
                raise ValueError(f"Dependency revision mismatch: {entry['id']}; existing files were preserved.")

    if not args.resume_native:
        run("generate", ["wsl", "-d", args.distro, "--exec", "timeout", "--kill-after=3s",
            str(args.generation_timeout) + "s", "python3",
            wsl_path(ROOT / "scripts/generate_from_rom.py"), "--rom", wsl_path(rom),
            "--workspace", wsl_path(workspace), "--dependency-root", wsl_path(deps),
            "--jobs", str(args.jobs)])
    generated = workspace / "normalized"
    build = workspace / "native"
    run("configure", [cmake, "-S", str(ROOT), "-B", str(build),
        "-G", "Visual Studio 17 2022", "-A", "x64", "-DBUILD_TESTING=OFF",
        "-DJFG_MSVC_GENERATED_COMPILE_JOBS=" + str(args.jobs),
        "-DJFG_ENABLE_GENERATED_CODE=ON", "-DJFG_BUILD_PHASE6_NATIVE_BOOT=ON",
        "-DJFG_BUILD_PHASE8_LIVE=ON", "-DJFG_ENABLE_RT64=ON",
        "-DJFG_GENERATED_ROOT=" + str(generated),
        "-DJFG_PHASE6_LIBULTRA_IDENTIFICATION=" + str(workspace / "libultra.json"),
        "-DJFG_PHASE8_PRIVATE_AUDIO_ADAPTER_ROOT=" + str(workspace / "audio"),
        "-DJFG_PHASE8_PRIVATE_AUDIO_RUNTIME_INCLUDE=" + str(deps / "N64ModernRuntime/librecomp/include"),
        "-DJFG_RT64_ROOT=" + str(deps / "rt64")])
    run("compile", [cmake, "--build", str(build), "--config", "Release",
        "--target", "jfg-native-boot", "--parallel", str(args.jobs)])
    executable = build / "Release/jfg-native-boot.exe"
    if not executable.is_file():
        raise RuntimeError("Build finished without the native executable.")
    (workspace / "status.json").write_text(json.dumps({"complete": True,
        "scope": "Compilation only; gameplay acceptance is separate",
        "rom_sha1": ROM_SHA1, "executable": str(executable), "steps": records}, indent=2) + "\n")
    print("Built: " + str(executable), flush=True)
    print("Keep this build local. It contains code generated from your ROM.", flush=True)
    if args.play:
        profile = Path(os.environ["LOCALAPPDATA"]) / "JFGRecomp/profiles/default"
        profile.mkdir(parents=True, exist_ok=True)
        environment = {k: v for k, v in os.environ.items() if not k.startswith("JFG_")}
        return subprocess.call([str(executable), "--rom", str(rom), "--save",
            str(profile / "jfg.flash"), "--controller-pak", str(profile / "controller-1.pak"),
            "--play"], cwd=executable.parent, env=environment)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
