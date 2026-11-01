"""Build matching PAL/JP ELF metadata privately; this does not build a playable runtime."""
from __future__ import annotations

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from scripts.rom_profiles import identify_rom, PAL_ROM, JAPAN_ROM
from scripts.regional_overlays import expand_regional_overlays
from scripts.probe_n64recomp_cpu import verify_private_work_directory

ROOT = Path(__file__).resolve().parents[2]


def regional_splat(text: str, region: str) -> str:
    profiles = {"pal": PAL_ROM, "jpn": JAPAN_ROM}
    if region not in profiles or "sha1: " + profiles[region].sha1 not in text:
        raise ValueError("Regional metadata does not match the pinned ROM profile.")
    # Retain original instructions directly. The pinned regional C headers are incomplete.
    text = re.sub(r"(\[0x[0-9A-Fa-f]+, )c(,)", r"\1asm\2", text)
    if region == "jpn":
        marker = "[0x9E4D0, bin]"
        if text.count(marker) != 1:
            raise ValueError("Unexpected Japanese executable-prefix metadata.")
        # BIN is emitted in DATA; TEXTBIN preserves its order before the audio ucode.
        text = text.replace(marker, "[0x9E4D0, textbin]")
    return text


def pal_linker_symbols(text: str) -> str:
    # The basic PAL map contains five unused shared aliases. Some boundaries are
    # recovered below; the asset lookup table still has no independently verified
    # extent, so retain the qualified removal of all five unused aliases.
    boundaries = ("overlay_1_ROM_START", "assets_lut_ROM_START", "assets_lut_ROM_END",
                  "symbolsTable_offsets_ROM_START", "symbolsTable_symbol_names_ROM_START")
    lines = text.splitlines()
    removed = [line for line in lines if any(name in line for name in boundaries)]
    if len(removed) != 5:
        raise ValueError("Unexpected PAL shared linker aliases.")
    return "\n".join(line for line in lines if line not in removed) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True,
                        help="New private Linux directory, outside the public source tree")
    parser.add_argument("--decomp", type=Path, default=ROOT / "tools/upstream/Jet-Force-Gemini")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("Run this metadata stage in WSL/Linux.")
    if not 1 <= args.jobs <= 8:
        parser.error("--jobs must be between 1 and 8")
    profile, rom, byte_order = identify_rom(args.rom.read_bytes(), normalize=True)
    if profile.code not in ("pal", "jpn"):
        parser.error("Use generate_from_rom.py for the supported US runtime.")
    workspace = args.workspace.resolve()
    verify_private_work_directory(workspace)
    if workspace.exists() or any(ch.isspace() for ch in str(workspace)):
        parser.error("Choose a new private workspace whose path contains no whitespace.")
    for tool in ("git", "make", "mips-linux-gnu-as", "mips-linux-gnu-readelf"):
        if not shutil.which(tool):
            parser.error("Missing Linux tool: " + tool)
    lock = json.loads((ROOT / "dependencies.lock.json").read_text())
    pin = next(entry["commit"] for entry in lock["repositories"] if entry["id"] == "jfg-decomp")
    actual_pin = subprocess.check_output(["git", "-C", str(args.decomp), "rev-parse", "HEAD"], text=True).strip()
    if actual_pin != pin:
        raise ValueError("Decomp revision differs from dependencies.lock.json.")
    workspace.mkdir(parents=True)
    result = {"region": profile.code, "rom_sha1": profile.sha1, "input_byte_order": byte_order,
              "decomp_commit": pin, "matching_rom": False, "native_playable": False, "steps": []}
    manifest = workspace / "metadata.json"
    def run(name: str, args: list[str], cwd: Path) -> None:
        start = time.monotonic()
        print(name, flush=True)
        with (workspace / (name + ".log")).open("w") as log:
            process = subprocess.run(args, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, timeout=900)
        result["steps"].append({"name": name, "exit_code": process.returncode,
                                "seconds": round(time.monotonic()-start, 3)})
        manifest.write_text(json.dumps(result, indent=2) + "\n")
        if process.returncode:
            raise RuntimeError(name + " failed; see the private workspace log.")
    decomp = workspace / "decomp"
    run("clone", ["git", "clone", "--no-hardlinks", str(args.decomp.resolve()), str(decomp)], workspace)
    run("submodules", ["git", "submodule", "update", "--init", "--recursive"], decomp)
    (decomp / "baseroms").mkdir(exist_ok=True)
    (decomp / "baseroms" / ("baserom." + profile.code + ".z64")).write_bytes(rom)
    yaml = decomp / "ver/splat" / ("jfg." + profile.code + ".yaml")
    yaml.write_text(expand_regional_overlays(
        regional_splat(yaml.read_text(), profile.code), rom, profile.code))
    if profile.code == "pal":
        symbols = decomp / "ver/symbols/undefined_syms.txt"
        symbols.write_text(pal_linker_symbols(symbols.read_text()))
    run("venv", [sys.executable, "-m", "venv", str(decomp / ".venv")], decomp)
    run("python-tools", [str(decomp / ".venv/bin/python3"), "-m", "pip", "install", "-r", "requirements.txt"], decomp)
    run("build-tools", ["make", "-C", "tools"], decomp)
    run("extract", ["make", "extract", "VERSION=" + profile.code, "COLOR=0"], decomp)
    src = "src_" + profile.code
    run("matching-elf", ["make", "-j" + str(args.jobs), "VERSION=" + profile.code, "COLOR=0",
                         "LIBULTRA_SRC_DIRS=", "HASM_DIRS=" + " ".join((src, src + "/hasm", src + "/hasm/ido"))], decomp)
    build = decomp / ("build_" + profile.code)
    rebuilt = build / ("jfg." + profile.code + ".z64")
    if rebuilt.read_bytes() != rom:
        raise ValueError("Regional reconstruction is not byte-for-byte identical.")
    elf = rebuilt.with_suffix(".elf")
    sections = subprocess.check_output(["mips-linux-gnu-readelf", "-SW", str(elf)], text=True)
    overlay_count = len(re.findall(r"\] \.overlay_\d+ +PROGBITS", sections))
    if overlay_count != 155:
        raise ValueError("Regional executable overlay coverage is incomplete.")
    result.update(matching_rom=True, elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
                  code_overlay_sections=overlay_count,
                  remaining=["Validate complete function boundaries, SDK mappings and CPU/RSP generation",
                             "Port and validate regional host addresses, timing and gameplay hooks",
                             "Qualify boot, controller/save behavior and regional transitions"])
    manifest.write_text(json.dumps(result, indent=2) + "\n")
    print("Matching " + profile.code + " metadata complete; native gameplay remains unqualified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
