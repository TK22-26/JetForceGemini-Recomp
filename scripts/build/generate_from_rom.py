#!/usr/bin/env python3
"""Local-only CPU/RSP generation stage for the Windows bootstrap prototype."""
from __future__ import annotations

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"


import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.transform_private_n64recomp_inputs import Layout, parse_headers, parse_records, infer_main_code_delta
from scripts.probe_n64recomp_cpu import verify_private_work_directory
from scripts.rom_profiles import identify_rom
from scripts.regional.reconstruction import reconstruct
from scripts.regional.pipeline import generate_cpu
from scripts.regional.generation_receipt import capture as capture_generation
from scripts.regional.audio_payloads import extract as extract_audio_payloads


def derive_layout(rom: bytes, map_text: str, context: dict) -> dict:
    # Compatibility API; the shared original-instruction owner defines domains.
    from scripts.regional.linker_layout import derive_layout as derive
    return asdict(derive(rom,map_text,context))


def audio_configuration(program: bytes, data: bytes) -> str:
    # The ROM's DMA descriptors specify source offset, length-minus-one and
    # IMEM destination. Hardware address masks are independent of game content.
    if len(data) < 18 or len(program) % 4:
        raise ValueError("Incomplete audio program")
    primary_offset, primary_info, secondary_offset, secondary_info = struct.unpack_from(">4I", data)
    primary_size, secondary_transfer_size = (primary_info >> 16) + 1, (secondary_info >> 16) + 1
    # Splat's text container includes alignment NOPs after the DMA payload.
    secondary_size = (secondary_transfer_size + 15) & ~15
    primary_address, secondary_address = primary_info & 0xFFFF, secondary_info & 0xFFFF
    common = secondary_address - primary_address
    if not (primary_offset == 0 and 0 < common < primary_size and
            primary_offset + primary_size == secondary_offset and
            secondary_offset + secondary_size == len(program) and
            primary_address >= 0x1000 and primary_address + primary_size == 0x2000 and
            secondary_address + secondary_size <= 0x2000 and common % 4 == 0):
        raise ValueError("Audio DMA descriptors do not describe the supported two-variant layout")
    if any(program[secondary_offset + secondary_transfer_size:]):
        raise ValueError("Audio container has nonzero alignment padding")
    # Decode the contiguous dispatch table, stopping at non-code data.
    targets = []
    for offset in range(16, len(data) - 1, 2):
        target = struct.unpack_from(">H", data, offset)[0]
        if not primary_address <= target < 0x2000 or target % 4:
            break
        targets.append(target)
    if len(targets) != 16 or len(set(targets)) != 16:
        raise ValueError("Audio command dispatch table did not close")
    return (
        f'text_offset = {primary_offset}\ntext_size = {primary_size}\n'
        f'text_address = {0x04000000 | primary_address}\n'
        'rom_file_path = "program.bin"\noutput_file_path = "./jfg-audio-probe.cpp"\n'
        'output_function_name = "jfg_audio_probe"\n'
        f'extra_indirect_branch_targets = {targets}\n\n[[overlay_slots]]\n'
        f'text_address = {0x04000000 | secondary_address}\n'
        f'overlays = [{{ offset = {common}, size = {primary_size-common} }}, '
        f'{{ offset = {secondary_offset}, size = {secondary_size} }}]\n')


def generate_audio(workspace: Path, model, rsp: Path, run, rom: bytes, reconstruction, cpu_generation) -> None:
    audio = workspace / "audio"
    audio.mkdir(exist_ok=True)
    payloads, payload_receipt = extract_audio_payloads(rom, model)
    program, audio_data = payloads["program"], payloads["data"]
    (audio / "payloads.json").write_text(json.dumps(payload_receipt, indent=2)+"\n")
    (audio / "program.bin").write_bytes(program)
    (audio / "input.toml").write_text(audio_configuration(program, audio_data))
    run("generate-audio", [str(rsp), "input.toml"], audio)
    generated = audio / "jfg-audio-probe.cpp"
    text = generated.read_text()
    marker = "        slots[slot] = overlay;"
    if text.count(marker) != 1:
        raise ValueError("Unexpected RSP generator overlay dispatcher")
    text = text.replace(marker, "        jfg_audio_probe_overlay_swaps++;\n"
        "        jfg_audio_probe_overlay_variant_one += overlay == 1;\n" + marker)
    text = "#include <cstdint>\nuint32_t jfg_audio_probe_overlay_swaps = 0;\nuint32_t jfg_audio_probe_overlay_variant_one = 0;\n" + text
    generated.write_text(text)
    for name in ("brokered-rsp.hpp", "production-audio-adapter.cpp"):
        shutil.copy2(ROOT / "src/bootstrap" / name, audio / name)
    (audio / "brokered-jfg-audio-probe.cpp").write_text(
        '#include "brokered-rsp.hpp"\n#include "jfg-audio-probe.cpp"\n')
    profile,_,_=identify_rom(rom)
    result={"schema_version":3,"kind":"jfg-regional-generation","complete":True,"revision_id":profile.revision_id,"rom_sha1":profile.sha1,"model_sha256":model.fingerprint(),"generation_input_sha256":cpu_generation["generation_input_sha256"],**capture_generation(workspace),"fresh_matching_elf":reconstruction["matching_rom"],"fresh_cpu":True,"fresh_audio":True,"tool_cache_reused":reconstruction["tool_cache_reused"],"rsp_compiler_sha256":hashlib.sha256(rsp.read_bytes()).hexdigest(),"scope":"Generation only; native gameplay qualification is separate"}
    (workspace/"generation.json").write_text(json.dumps(result,indent=2)+"\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--dependency-root", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("Run this stage inside WSL/Linux")
    workspace, deps = args.workspace.resolve(), args.dependency_root.resolve()
    verify_private_work_directory(workspace)
    profile, rom, input_byte_order = identify_rom(args.rom.read_bytes(), normalize=True)
    if not 1 <= args.jobs <= 32: parser.error("--jobs must be 1..32")
    if any((workspace/name).exists() for name in ("original-private.z64", "generation.json", "metadata", "context", "program", "normalized", "audio", "reconstruction.json", "cpu-generation.json")):
        raise ValueError("Generation output already contains stage artifacts; choose a fresh workspace")
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "original-private.z64").write_bytes(rom)
    for name in ("git", "make", "gcc", "mips-linux-gnu-as", "mips-linux-gnu-objcopy", "readelf", "cmake", "ninja"):
        if not shutil.which(name):
            raise ValueError("Required WSL tool missing: " + name)
    # Make/IDO cannot reliably build in paths with spaces. A fresh private
    # Linux directory also prevents reuse of any pre-generated game output.
    scratch = Path(tempfile.mkdtemp(prefix="jfg-rom-build-"))
    (workspace / "linux-workspace.txt").write_text(str(scratch) + "\n")

    def run(name: str, command: list[str], cwd: Path = ROOT) -> None:
        print(name, flush=True)
        with (workspace / (name + ".log")).open("w") as log:
            subprocess.run(command, cwd=cwd, check=True, stdout=log, stderr=subprocess.STDOUT)

    decomp = scratch / "decomp"
    elf, linker_map, reconstruction = reconstruct(rom, deps / "Jet-Force-Gemini", decomp, args.jobs, run)
    reconstruction["input_byte_order"] = input_byte_order
    (workspace / "reconstruction.json").write_text(json.dumps(reconstruction, indent=2)+"\n")
    lock = json.loads((ROOT / "dependencies.lock.json").read_text())
    recomp_pin = next(v["commit"] for v in lock["repositories"] if v["id"] == "n64recomp")
    if subprocess.check_output(["git", "-C", str(deps / "N64Recomp"), "rev-parse", "HEAD"], text=True).strip() != recomp_pin:
        raise ValueError("Recompiler source differs from the dependency pin")
    # Prepare the exact patched recompiler in its own checkout.
    recomp = scratch / "N64Recomp"
    run("clone-recompiler", ["git", "clone", "--no-hardlinks", str(deps / "N64Recomp"), str(recomp)])
    run("recompiler-submodules", ["git", "submodule", "update", "--init", "--recursive"], recomp)
    run("patch-recompiler", [sys.executable, str(ROOT / "scripts/build/apply_n64recomp_patchset.py"),
        "--target", str(recomp), "--project-root", str(ROOT)])
    run("configure-recompiler", ["cmake", "-S", str(recomp), "-B", str(recomp / "build"),
        "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release"])
    run("build-recompiler", ["cmake", "--build", str(recomp / "build"), "--target", "N64RecompCLI", "RSPRecomp", "-j", str(args.jobs)])
    cpu, rsp = recomp / "build/N64Recomp", recomp / "build/RSPRecomp"
    model, cpu_generation = generate_cpu(rom, elf, linker_map, cpu, recomp / "include/recomp.h", workspace, run)
    generate_audio(workspace, model, rsp, run, rom, reconstruction, cpu_generation)
    print("Fresh CPU and audio generation complete.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
