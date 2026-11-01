#!/usr/bin/env python3
"""Build an exact US/PAL/JP native candidate locally through shared contracts."""
from __future__ import annotations

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"


import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
from scripts.build_paths import windows_cache, check_binary_path
from scripts.runtime_identity import write_identity
from scripts.rom_profiles import identify_rom
from scripts.regional.generation_receipt import verify as verify_generation
from scripts.native_program_identity import capture_source
from scripts import program_bundle

ROOT = Path(__file__).resolve().parents[2]
NAMES = {"jfg-decomp": "Jet-Force-Gemini", "n64recomp": "N64Recomp",
         "n64modernruntime": "N64ModernRuntime", "rt64": "rt64"}


def validate_rom(path: Path) -> str:
    if not path.is_file():raise ValueError("Select an existing original US, PAL or Japanese ROM.")
    return identify_rom(path.read_bytes(),normalize=True)[0].sha1


def require_build_admission(profile,*,candidate=False,play=False):
    if not profile.native_supported and (not candidate or play):
        raise ValueError(profile.title+" is not admitted for native Play. Use --candidate only for local development builds; qualification is separate.")


def prepare_play_profile(shared,profile):
    # Same versioned namespace marker as the launcher's RegionalStorage.
    # Invocation is only after exact ROM/bundle verification and admission.
    shared=Path(os.path.abspath(shared));target=shared if profile.code=='us' else shared/'revisions'/profile.revision_id
    def ordinary(path):
        try: info=path.lstat()
        except FileNotFoundError:return
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400):
            raise ValueError('Profile paths must not be links or reparse points')
    for path in (shared,*([] if profile.code=='us' else [shared/'revisions',target])):
        ordinary(path)
        path.mkdir(parents=True,exist_ok=True)
        ordinary(path)
    marker=target/'rom-revision.txt';identity='jfg-save-namespace-1\n'+profile.revision_id+'\n'+profile.sha1+'\n'
    ordinary(marker)
    if not marker.exists():
        if profile.code!='us' and any((target/name).exists() for name in ('jfg.flash','controller-1.pak')):raise ValueError('Unmarked regional saves cannot be assigned a revision')
        temporary=target/('rom-revision.'+uuid.uuid4().hex+'.tmp')
        try:
            with temporary.open('x',encoding='ascii',newline='\n') as output:output.write(identity);output.flush();os.fsync(output.fileno())
            try:os.link(temporary,marker)
            except FileExistsError:pass
        finally:
            if temporary.exists():temporary.unlink()
    ordinary(marker)
    if marker.stat().st_size>256 or marker.read_bytes()!=identity.encode('ascii'):raise ValueError('Save profile belongs to another ROM revision')
    return target


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
    parser.add_argument("--distro", help="Optional WSL distribution; defaults to the installed default")
    parser.add_argument("--jobs", type=int, default=min(os.cpu_count() or 4, 8))
    parser.add_argument("--dependency-root", type=Path,
                        help="Optional existing pinned upstream source/tool cache")
    parser.add_argument("--build-root", type=Path, help="Optional short writable Windows build-cache folder")
    parser.add_argument("--play", action="store_true")
    parser.add_argument("--candidate", action="store_true", help="Build an unqualified recognized revision locally; never enables Play")
    parser.add_argument("--profile", type=Path, help="Shared save profile root for admitted --play")
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
    validate_rom(rom)
    profile,_,_=identify_rom(rom.read_bytes(),normalize=True)
    require_build_admission(profile,candidate=args.candidate,play=args.play)  # Before output or profile writes.
    cmake = find_cmake()
    for tool in ("git", "wsl"):
        if not shutil.which(tool):
            raise ValueError(f"Required tool missing: {tool}")
    cache = windows_cache(ROOT, args.build_root)
    deps = (args.dependency_root or cache / "d").resolve()
    if args.resume_native:
        workspace = args.resume_native.resolve()
        if not any(workspace.is_relative_to(parent.resolve()) for parent in [cache / "w", ROOT / "tools/private/local-builds"]):
            raise ValueError("Resume requires this checkout's build cache or its legacy tools/private/local-builds folder.")
        verify_generation(workspace,profile)
    else:
        workspace = cache / "w" / uuid.uuid4().hex[:12]
        workspace.mkdir(parents=True, exist_ok=False)
    build = check_binary_path(workspace / ("native" if args.resume_native and (workspace / "native").exists() else "n"))
    print("Local build workspace: " + str(workspace), flush=True)
    status_file = workspace / "status.json"
    records: list[dict] = (json.loads(status_file.read_text()).get("steps", [])
                           if args.resume_native and status_file.is_file() else [])
    status_file.write_text(json.dumps({"complete": False, "steps": records}, indent=2) + "\n")

    def run(name: str, command: list[str], cwd: Path = ROOT) -> None:
        print(name, flush=True)
        print("JFG-SUPPORT setup_step=" + name, flush=True)
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
                    # Emit only stable diagnostics; raw compiler output stays local.
                    for token, category in {"Filename too long": "path-too-long", "exceeds the OS max path limit": "path-too-long", "Permission denied": "permission-denied", "Could not resolve": "dns-failed", "No space left": "disk-full", "CMake Error": "cmake-failed", "0x80370102": "virtualization-unavailable"}.items():
                        if token.lower() in line.lower():
                            print("JFG-SUPPORT setup_error=" + category, flush=True)
                    for error_code in re.findall(r"\b(?:error|fatal error) (C[0-9]{4}|LNK[0-9]{4}|MSB[0-9]{4})\b", line, re.I):
                        print("JFG-SUPPORT compiler_error=" + error_code.lower(), flush=True)
                    if name == "generate" and re.fullmatch(r"[a-z][a-z-]+\n?", line):
                        print("  " + line.strip(), flush=True)
                code = process.wait()
        records.append({"step": name, "exit_code": code,
                        "seconds": round(time.monotonic() - started, 3)})
        (workspace / "status.json").write_text(json.dumps(
            {"complete": False, "steps": records}, indent=2) + "\n")
        print("JFG-SUPPORT setup_exit=0x" + format(code & 0xffffffff, "08x"), flush=True)
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
                run("clone-" + entry["id"], ["git", "clone", "--config", "core.autocrlf=false", "--config", "core.longpaths=true", "--no-checkout", entry["url"], str(dest)])
                run("pin-" + entry["id"], ["git", "-C", str(dest), "checkout", "--detach", entry["commit"]])

    for entry in lock["repositories"]:
        if entry["id"] in NAMES:
            dest = deps / NAMES[entry["id"]]
            head = subprocess.check_output(["git", "-C", str(dest), "rev-parse", "HEAD"], text=True).strip()
            if head != entry["commit"]:
                raise ValueError(f"Dependency revision mismatch: {entry['id']}; existing files were preserved.")
            if not args.dependency_root:
                run("submodules-" + entry["id"], ["git", "-c", "core.autocrlf=false", "-c", "core.longpaths=true", "-C", str(dest), "submodule", "update", "--init", "--recursive"])

    if not args.resume_native:
        run("generate", ["wsl"] + (["-d",args.distro] if args.distro else []) + ["--exec", "timeout", "--kill-after=3s",
            str(args.generation_timeout) + "s", "python3",
            wsl_path(ROOT / "scripts/build/generate_from_rom.py"), "--rom", wsl_path(rom),
            "--workspace", wsl_path(workspace), "--dependency-root", wsl_path(deps),
            "--jobs", str(args.jobs)])
    verify_generation(workspace,profile)
    generated = workspace / "normalized"
    source_inputs=capture_source(ROOT)
    source_input_path=workspace/"native-source-inputs.json"
    source_input_path.write_text(json.dumps(source_inputs,indent=2)+"\n")
    run("configure", [cmake, "-S", str(ROOT), "-B", str(build),
        "-G", "Visual Studio 17 2022", "-A", "x64", "-DBUILD_TESTING=OFF", "-DJFG_SUPPORT_SYMBOLS=ON",
        "-DJFG_MSVC_GENERATED_COMPILE_JOBS=" + str(args.jobs),
        "-DJFG_MSVC_NATIVE_COMPILE_JOBS=" + str(min(args.jobs,8)),
        "-DJFG_ENABLE_GENERATED_CODE=ON", "-DJFG_BUILD_PHASE6_NATIVE_BOOT=ON",
        "-DJFG_BUILD_PHASE8_LIVE=ON", "-DJFG_ENABLE_RT64=ON",
        "-DJFG_GENERATED_ROOT=" + str(generated),
        "-DJFG_PHASE8_PRIVATE_AUDIO_ADAPTER_ROOT=" + str(workspace / "audio"),
        "-DJFG_PHASE8_PRIVATE_AUDIO_RUNTIME_INCLUDE=" + str(deps / "N64ModernRuntime/librecomp/include"),
        "-DJFG_RT64_ROOT=" + str(deps / "rt64")])
    run("compile", [cmake, "--build", str(build), "--config", "Release",
        "--target", "jfg-native-boot", "--parallel", str(args.jobs)])
    executable = build / "Release/jfg-native-boot.exe"
    if not executable.is_file():
        raise RuntimeError("Build finished without the native executable.")
    if capture_source(ROOT)!=source_inputs:raise ValueError("Native source changed during compilation; preserve this build and rebuild from a stable source snapshot")
    receipt_path=workspace/'native-build.json'
    receipt={'complete':True,'scope':'Compilation only; gameplay acceptance is separate','revision_id':profile.revision_id,'rom_sha1':profile.sha1,
        'executable':str(executable),'sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),'changed_source_inputs':[],
        'native_identity_receipt':str(build/'native-identity/Release/inputs.json'),'steps':records}
    receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    bundle=workspace/'bundles'/uuid.uuid4().hex/profile.revision_id;bundle.mkdir(parents=True,exist_ok=False)
    for name in program_bundle.RUNTIME_FILES:
        source=executable.parent/name
        if source.is_file():shutil.copy2(source,bundle/name)
    program_bundle.create(bundle,generated,receipt_path,source_input_path,ROOT)
    executable=bundle/'jfg-native-boot.exe';write_identity(executable,ROOT)
    status_file.write_text(json.dumps(dict(receipt,executable=str(executable),bundle=str(bundle)),indent=2)+'\n')
    print("Built: " + str(executable), flush=True)
    print("Keep this build local. Native gameplay qualification is separate.", flush=True)
    if args.play:
        program_bundle.verify(bundle,profile.revision_id)
        canonical=workspace/'original-private.z64'
        if identify_rom(canonical.read_bytes())[0].revision_id!=profile.revision_id:raise ValueError('Canonical ROM changed before launch')
        data_root=Path(os.environ['JFG_DATA_ROOT']) if os.environ.get('JFG_DATA_ROOT') else Path(os.environ['LOCALAPPDATA'])/'JFGRecomp'
        save_profile=prepare_play_profile(args.profile or data_root/'profiles/default',profile)
        environment={k:v for k,v in os.environ.items() if not k.upper().startswith('JFG_')}
        return subprocess.call([str(executable),'--rom',str(canonical),'--save',str(save_profile/'jfg.flash'),
            '--controller-pak',str(save_profile/'controller-1.pak'),'--play'],cwd=bundle,env=environment)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
