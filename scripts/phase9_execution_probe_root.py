"""Generate a private instruction-observation root through N64Recomp hooks.

Run under WSL. This does not rewrite generated instruction comments, install
timing costs, or change the source root. Output is diagnostic, not acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
HOOK_LINE = re.compile(r"[ \t]*jfg_phase9_execution_probe\([0-9]+U, 0x[0-9a-f]{8}U, 0x[0-9a-f]{8}U, ctx\);\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_bodies(control, observed):
    """Remove only our generated observations; require otherwise identical C."""
    manifest = json.loads((control / "sources.json").read_text())
    paths = manifest["baseline_body_sources"] + manifest["alternate_entry_thunk_sources"]
    differing = []
    for name in paths:
        # Hook emission can change indentation of a duplicated delay-slot
        # comment. Preserve all intra-line text and ignore only indentation.
        left = [line.strip() for line in (control / name).read_text().splitlines()]
        right = [line.strip() for line in HOOK_LINE.sub("", (observed / name).read_text()).splitlines()]
        if left != right:
            differing.append(name)
    return {"bodies": len(paths), "differing_bodies": differing,
            "instruction_hooks_only": not differing}


def hook_rows(symbols, rom):
    seen = set()
    for section_id, section in enumerate(symbols["section"]):
        for function in section["functions"]:
            name, start, size = function["name"], function["vram"], function["size"]
            if name in seen or size <= 0 or size % 4 or start % 4:
                raise ValueError("invalid or duplicate function")
            seen.add(name)
            offset = section["rom"] + start - section["vram"]
            if offset < 0 or offset + size > len(rom):
                raise ValueError("function outside pinned ROM")
            for byte in range(0, size, 4):
                word = int.from_bytes(rom[offset + byte:offset + byte + 4], "big")
                pc = start + byte
                text = f"jfg_phase9_execution_probe({section_id}U, 0x{pc:08x}U, 0x{word:08x}U, ctx);"
                yield ('[[patches.hook]]\n' + f'func = {json.dumps(name)}\n' +
                       f'before_vram = 0x{pc:08x}\ntext = {json.dumps(text)}\n')


def run(args):
    guest_links = getattr(args, "guest_links", False)
    guest_cpu_state = getattr(args, "guest_cpu_state", False)
    guest_returns = getattr(args, "guest_returns", False)
    guest_idle = getattr(args, "guest_idle", False)
    if guest_returns and not guest_links:
        raise ValueError("guest returns require architectural links")
    if (guest_links or guest_cpu_state or guest_returns or guest_idle) and args.control_root is not None:
        raise ValueError("guest CPU state changes semantics; an observation-only control comparison is invalid")
    private = (ROOT / "tools/private").resolve(strict=True)
    output = args.output.resolve()
    if not output.is_relative_to(private) or output.exists():
        raise ValueError("output must be a new private directory")
    inputs = {key: getattr(args, key).resolve(strict=True) for key in
              ("symbols", "rom", "original_context", "runtime_manifest", "recomp_header", "recompiler")}
    if digest(inputs["rom"]) != args.rom_sha256:
        raise ValueError("patched ROM digest mismatch")
    if digest(inputs["recompiler"]) != args.recompiler_sha256:
        raise ValueError("recompiler digest mismatch")
    symbols = tomllib.loads(inputs["symbols"].read_text())
    rom = inputs["rom"].read_bytes()
    output.mkdir()
    config = output / "instrumented.toml"
    count = 0
    with config.open("w") as stream:
        stream.write('[input]\n' +
                     f'symbols_file_path = {json.dumps(str(inputs["symbols"]))}\n' +
                     f'rom_file_path = {json.dumps(str(inputs["rom"]))}\n' +
                     'output_func_path = "raw"\n' +
                     'indirect_decision_sidecar_path = "raw/indirect_decisions.json"\n' +
                     'functions_per_output_file = 50\n' +
                     'unpaired_lo16_warnings = false\n' +
                     'use_lookup_for_all_function_calls = true\n' +
                     ('emit_guest_link_registers = true\n' if guest_links else '') +
                     ('emit_guest_cpu_state = true\n' if guest_cpu_state else '') +
                     ('emit_guest_dynamic_returns = true\n' if guest_returns else '') +
                     ('emit_guest_idle_loops = true\n' if guest_idle else '') + '[patches]\n')
        for row in hook_rows(symbols, rom):
            stream.write(row)
            count += 1
    with (output / "generation.log").open("w") as log:
        subprocess.run([str(inputs["recompiler"]), str(config)], check=True,
                       stdout=log, stderr=subprocess.STDOUT, timeout=600)
    with (output / "normalization.log").open("w") as log:
        subprocess.run([sys.executable, str(ROOT / "scripts/build_private_generated_root.py"),
                        "--raw-generated", str(output / "raw"),
                        "--symbols", str(inputs["symbols"]),
                        "--original-context", str(inputs["original_context"]),
                        "--runtime-manifest", str(inputs["runtime_manifest"]),
                        "--recomp-header", str(inputs["recomp_header"]),
                        "--output", str(output / "root")], check=True,
                       stdout=log, stderr=subprocess.STDOUT, timeout=600)
    # Declare at file scope; block-scope extern declarations trigger MSVC
    # C4210 under the generated root's warning-as-error policy.
    header = output / "root/funcs.h"
    declaration = ('\n#ifdef __cplusplus\nextern "C" {\n#endif\n'
                   'void jfg_phase9_execution_probe(unsigned, unsigned, unsigned, void*);\n'
                   '#ifdef __cplusplus\n}\n#endif\n')
    header.write_text(header.read_text() + declaration)
    result = {"kind": "jfg-execution-observation-root", "acceptance": False,
              "instruction_sites": count, "inputs": {key: digest(value) for key, value in inputs.items()},
              "config_sha256": digest(config), "profile": "observation-only-no-timing-costs"}
    result["guest_link_registers"] = guest_links
    result["guest_cpu_state"] = guest_cpu_state
    result["guest_dynamic_returns"] = guest_returns
    result["guest_idle_loops"] = guest_idle
    if args.control_root is not None:
        result["control_comparison"] = compare_bodies(args.control_root.resolve(strict=True), output / "root")
        if not result["control_comparison"]["instruction_hooks_only"]:
            raise ValueError("generated bodies changed beyond observation hooks")
    (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    for name in ("symbols", "rom", "original-context", "runtime-manifest", "recomp-header", "recompiler"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--recompiler-sha256", required=True)
    parser.add_argument("--control-root", type=Path)
    parser.add_argument("--guest-links", action="store_true")
    parser.add_argument("--guest-cpu-state", action="store_true")
    parser.add_argument("--guest-returns", action="store_true")
    parser.add_argument("--guest-idle", action="store_true")
    print(json.dumps(run(parser.parse_args())))
