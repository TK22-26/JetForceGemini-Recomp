"""Generate paired, opt-in game instruction hooks; run under WSL.

The existing execution observer still owns CPU/device work. New entry hooks
run after it returns (including exception resumption); ordinary effect hooks
run at the compiler's qualified effect boundary. ERET needs the runtime's
pre-handoff callback. Other excluded operations must reject a live capture.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

from scripts.phase9_execution_probe_root import ROOT, digest


ENTRY = re.compile(r"[ \t]*jfg_phase9_instruction_effect_entry\([0-9]+U, 0x[0-9a-f]{8}U, 0x[0-9a-f]{8}U, [0-2]U, ctx\);\n")
EFFECT = re.compile(r"[ \t]*jfg_phase9_instruction_effect\([0-9]+U, 0x[0-9a-f]{8}U, 0x[0-9a-f]{8}U, ctx\);\n")


def qualification(word):
    """0 ordinary effect, 1 dedicated ERET boundary, 2 unqualified callback.

    The compiler remains authoritative for decoding/after-hook eligibility.
    This list routes its explicitly excluded operations, not arbitrary invalid
    opcodes around compiler validation.
    """
    if type(word) is not int or not 0 <= word <= 0xffffffff:
        raise ValueError("invalid instruction word")
    if word == 0x42000018:
        return 1
    primary = word >> 26
    if (primary == 0 and word & 63 in (12, 13)) or primary in (18, 50, 54, 58, 62):
        return 2
    return 0


def sites(symbols, rom):
    seen = set()
    for section_id, section in enumerate(symbols["section"]):
        for function in section["functions"]:
            name, start, size = function["name"], function["vram"], function["size"]
            if (not isinstance(name, str) or not name or name in seen or
                    type(start) is not int or type(size) is not int or
                    not 0 < start <= 0xffffffff or start % 4 or size <= 0 or size % 4 or
                    start + size > 0x100000000):
                raise ValueError("invalid or duplicate instruction function")
            seen.add(name)
            offset = section["rom"] + start - section["vram"]
            if offset < 0 or offset + size > len(rom):
                raise ValueError("instruction function outside pinned ROM")
            for byte in range(0, size, 4):
                word = int.from_bytes(rom[offset + byte:offset + byte + 4], "big")
                yield {"section": section_id, "function": name, "pc": start + byte,
                       "opcode": word, "qualification": qualification(word)}


def hooks(site):
    name, section, pc, word, mode = (site[k] for k in
        ("function", "section", "pc", "opcode", "qualification"))
    args = f"{section}U, 0x{pc:08x}U, 0x{word:08x}U"
    # Two separate statements, preserving the existing before-hook exactly.
    before = (f"jfg_phase9_execution_probe({args}, ctx);\n"
              f"    jfg_phase9_instruction_effect_entry({args}, {mode}U, ctx);")
    row = ('[[patches.hook]]\n' + f'func = {json.dumps(name)}\n' +
           f'before_vram = 0x{pc:08x}\ntext = {json.dumps(before)}\n')
    if mode == 0:
        row += ('[[patches.hook]]\n' + f'func = {json.dumps(name)}\n' +
                f'after_vram = 0x{pc:08x}\n' +
                f'text = {json.dumps(f"jfg_phase9_instruction_effect({args}, ctx);")}\n')
    return row


def compare_bodies(control, observed):
    paths = []
    for base in (control, observed):
        manifest = json.loads((base / "sources.json").read_text())
        paths.append(manifest["baseline_body_sources"] + manifest["alternate_entry_thunk_sources"])
    if paths[0] != paths[1] or len(set(paths[0])) != len(paths[0]):
        raise ValueError("instruction-effect body inventory changed")
    differing = []
    for name in paths[0]:
        left = [line.strip() for line in (control / name).read_text().splitlines()]
        right = [line.strip() for line in EFFECT.sub("", ENTRY.sub("", (observed / name).read_text())).splitlines()]
        if left != right:
            differing.append(name)
    return {"bodies": len(paths[0]), "differing_bodies": differing,
            "instruction_effect_hooks_only": not differing}


def run(args):
    private = (ROOT / "tools/private").resolve(strict=True)
    output = args.output.resolve()
    if not output.is_relative_to(private) or output.exists():
        raise ValueError("output must be a new private directory")
    keys = ("symbols", "rom", "original_context", "runtime_manifest", "recomp_header", "recompiler")
    inputs = {key: getattr(args, key).resolve(strict=True) for key in keys}
    before = {key: digest(value) for key, value in inputs.items()}
    if before["rom"] != args.rom_sha256 or before["recompiler"] != args.recompiler_sha256:
        raise ValueError("patched ROM or recompiler digest mismatch")
    control = args.control_root.resolve(strict=True)
    control_manifest = json.loads((control / "sources.json").read_text())
    body_names = control_manifest["baseline_body_sources"] + control_manifest["alternate_entry_thunk_sources"]
    control_pins = {name: digest(control / name) for name in ["sources.json", *body_names]}
    symbols = tomllib.loads(inputs["symbols"].read_text())
    rom = inputs["rom"].read_bytes()
    output.mkdir()
    config = output / "instrumented.toml"
    counts = [0, 0, 0]
    exceptions = []
    with config.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write('[input]\n' +
            f'symbols_file_path = {json.dumps(str(inputs["symbols"]))}\n' +
            f'rom_file_path = {json.dumps(str(inputs["rom"]))}\n' +
            'output_func_path = "raw"\n' +
            'indirect_decision_sidecar_path = "raw/indirect_decisions.json"\n' +
            'functions_per_output_file = 50\nunpaired_lo16_warnings = false\n' +
            'use_lookup_for_all_function_calls = true\n' +
            'emit_guest_link_registers = true\nemit_guest_cpu_state = true\n' +
            'emit_guest_dynamic_returns = true\nemit_guest_idle_loops = true\n[patches]\n')
        for site in sites(symbols, rom):
            stream.write(hooks(site))
            counts[site["qualification"]] += 1
            if site["qualification"]:
                exceptions.append(site)
    for filename, command in (
        ("generation.log", [str(inputs["recompiler"]), str(config)]),
        ("normalization.log", [sys.executable, str(ROOT / "scripts/build_private_generated_root.py"),
            "--raw-generated", str(output / "raw"), "--symbols", str(inputs["symbols"]),
            "--original-context", str(inputs["original_context"]),
            "--runtime-manifest", str(inputs["runtime_manifest"]),
            "--recomp-header", str(inputs["recomp_header"]), "--output", str(output / "root")]),
    ):
        with (output / filename).open("w") as log:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    header = output / "root/funcs.h"
    header.write_text(header.read_text() + '\n#ifdef __cplusplus\nextern "C" {\n#endif\n'
        'void jfg_phase9_execution_probe(unsigned, unsigned, unsigned, void*);\n'
        'void jfg_phase9_instruction_effect_entry(unsigned section, unsigned pc, unsigned opcode, unsigned mode, void* ctx);\n'
        'void jfg_phase9_instruction_effect(unsigned, unsigned, unsigned, void*);\n'
        '#ifdef __cplusplus\n}\n#endif\n')
    comparison = compare_bodies(control, output / "root")
    if not comparison["instruction_effect_hooks_only"]:
        raise ValueError("game bodies changed beyond instruction-effect hooks")
    if (before != {key: digest(value) for key, value in inputs.items()} or
            control_pins != {name: digest(control / name) for name in control_pins}):
        raise ValueError("instruction-effect generation inputs changed")
    excluded = output / "dedicated-or-unqualified-sites.json"
    excluded.write_text(json.dumps(exceptions, indent=2) + "\n")
    result = {"schema": 1, "kind": "jfg-instruction-effect-root", "inputs": before,
        "instruction_sites": sum(counts), "ordinary_effect_sites": counts[0],
        "dedicated_eret_sites": counts[1], "unqualified_sites": counts[2],
        "excluded_inventory_sha256": digest(excluded), "config_sha256": digest(config),
        "control": {"root": str(control), "files": control_pins},
        "control_comparison": comparison, "acceptance": False,
        "game_capture_qualified": False, "hardware_retirement_qualified": False}
    (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    for name in ("symbols", "rom", "original-context", "runtime-manifest", "recomp-header", "recompiler", "control-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--recompiler-sha256", required=True)
    result = run(parser.parse_args())
    print(json.dumps({key: result[key] for key in ("kind", "instruction_sites",
        "ordinary_effect_sites", "dedicated_eret_sites", "unqualified_sites",
        "control_comparison", "acceptance")}))


if __name__ == "__main__":
    main()
