"""ROM-free proof of post-effect hooks, not a game retirement qualification.

Run under Linux/WSL with an isolated compiler. Preserve both generated bodies,
sanitized executions, rejected configurations and all input digests.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(output, recompiler, control_recompiler, include):
    output = output.resolve()
    recompiler, control_recompiler, include = (p.resolve(strict=True) for p in (recompiler, control_recompiler, include))
    if not output.is_relative_to(ROOT / "tools/private") or output.exists():
        raise ValueError("use a new private output directory")
    output.mkdir()
    receipts = []

    def command(argv, *, expect_failure=False):
        argv = list(map(str, argv))
        result = subprocess.run(argv, cwd=output, capture_output=True, text=True, timeout=180)
        index = len(receipts)
        (output / f"command-{index}.stdout").write_text(result.stdout)
        (output / f"command-{index}.stderr").write_text(result.stderr)
        receipts.append({"argv": argv, "exit_code": result.returncode})
        if (result.returncode != 0) != expect_failure:
            raise ValueError(f"unexpected command {index} result: {result.returncode}: {result.stderr[-1500:]}")
        return result

    def config(elf, generated):
        return ["[input]", f"elf_path = {json.dumps(str(elf))}",
                f"output_func_path = {json.dumps(str(generated))}", "use_mdebug = false",
                "use_lookup_for_all_function_calls = true", "emit_guest_link_registers = true",
                "emit_guest_dynamic_returns = true", "[patches]"]

    def hook(name, pc, key, phase):
        text = ("/* JFG_EFFECT_FIXTURE */ extern void effect_observe(unsigned, unsigned, uint8_t*, recomp_context*); "
                f"effect_observe({phase}U, 0x{pc:08x}U, rdram, ctx);")
        return ["[[patches.hook]]", f"func = {json.dumps(name)}", f"{key} = 0x{pc:08x}", f"text = {json.dumps(text)}"], text

    fixture = ROOT / "tests/fixtures/instruction_effects.S"
    driver = ROOT / "tests/generated_instruction_effects.cpp"
    try:
        command(["mips-linux-gnu-as", "-march=vr4300", "-32", "-o", "test.o", fixture])
        command(["mips-linux-gnu-ld", "-Ttext=0x80001000", "-e", "effect_store", "-o", "test.elf", "test.o"])
        symbols = command(["mips-linux-gnu-nm", "-S", "test.elf"]).stdout
        functions = [(int(a, 16), int(size, 16), name) for a, size, name in
                     re.findall(r"^([0-9a-f]+) ([0-9a-f]+) T (effect_\w+)$", symbols, re.M)]
        if len(functions) != 9 or any(size == 0 or size % 4 for _, size, _ in functions):
            raise ValueError("incomplete effect fixture symbols")
        (output / "effect_addresses.h").write_text("".join(
            f"#define {name.upper()} 0x{address:08x}U\n" for address, _, name in functions))
        hook_lines = set()
        generated = {}
        outputs = {}
        flags = ["-O1", "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer"]
        for name, compiler, enabled in (("baseline", control_recompiler, False),
                                        ("control", recompiler, False), ("observed", recompiler, True)):
            lines = config("test.elf", name)
            if enabled:
                for start, size, function in functions:
                    for pc in range(start, start + size, 4):
                        for key, phase in (("before_vram", 0), ("after_vram", 1)):
                            added, text = hook(function, pc, key, phase)
                            lines += added
                            hook_lines.add(text)
            path = output / (name + ".toml")
            path.write_text("\n".join(lines) + "\n")
            command([compiler, path])
            sources = sorted((output / name).glob("*.c"))
            if not sources:
                raise ValueError("compiler produced no fixture bodies")
            generated[name] = {p.name: p.read_text() for p in sources}
            objects = []
            for index, source in enumerate(sources):
                obj = output / f"{name}-{index}.o"
                command(["gcc", "-std=c11", *flags, "-I", include, "-c", source, "-o", obj])
                objects.append(obj)
            binary = output / (name + "-test")
            command(["g++", "-std=c++20", *flags, f"-DEFFECT_HOOKS={int(enabled)}", "-I", include,
                     "-I", output, driver, *objects, "-o", binary])
            outputs[name] = command([binary]).stdout
        if generated["baseline"] != generated["control"]:
            raise ValueError("disabled effect hooks changed generated C")
        def stripped(bodies):
            return {name: [line.strip() for line in text.splitlines() if line.strip() not in hook_lines]
                    for name, text in bodies.items()}
        if stripped(generated["control"]) != stripped(generated["observed"]):
            raise ValueError("observed bodies changed beyond exact configured hook text/indentation")
        if len(set(outputs.values())) != 1 or not outputs["observed"].endswith("passed\t12\n"):
            raise ValueError("control/observed results or event checks differ")

        # Negative cases must be rejected by the relevant gate, not an unrelated error.
        rejected = []
        for name, body, reason in (("eret", "eret", "unqualified"), ("syscall", "syscall", "unqualified"),
                                   ("break", "break", "unqualified"), ("idle", "b rejected\n nop", "idle loops")):
            assembly = output / (name + ".S")
            assembly.write_text(".set noreorder\n.text\n.globl rejected\n.type rejected,@function\nrejected:\n " +
                                body + "\n nop\n.size rejected,.-rejected\n")
            command(["mips-linux-gnu-as", "-march=vr4300", "-32", "-o", name + ".o", assembly])
            command(["mips-linux-gnu-ld", "-Ttext=0x80001000", "-e", "rejected", "-o", name + ".elf", name + ".o"])
            path = output / (name + ".toml")
            lines = config(name + ".elf", name + "-generated") + hook("rejected", 0x80001000, "after_vram", 1)[0]
            path.write_text("\n".join(lines) + "\n")
            result = command([recompiler, path], expect_failure=True)
            if reason not in result.stderr:
                raise ValueError("unrelated rejected-instruction failure: " + result.stderr)
            rejected.append(name)
        start, _, function = functions[0]
        for name, fields, reason in (
                ("dual", f"before_vram = 0x{start:x}\nafter_vram = 0x{start:x}", "no before_vram"),
                ("unaligned", f"after_vram = 0x{start+1:x}", "word-aligned"),
                ("wrong-type", 'after_vram = "bad"', "uint32"),
                ("negative", "after_vram = -1", "uint32"),
                ("outside", "after_vram = 0x80400000", "contain")):
            path = output / (name + ".toml")
            lines = config("test.elf", name + "-generated")
            lines += ["[[patches.hook]]", f"func = {json.dumps(function)}", fields, 'text = "/* invalid */"']
            path.write_text("\n".join(lines) + "\n")
            result = command([recompiler, path], expect_failure=True)
            if reason not in result.stderr:
                raise ValueError("unrelated rejected-configuration failure: " + result.stderr)
            rejected.append(name)
        inputs = [fixture, driver, Path(__file__), recompiler, control_recompiler, include / "recomp.h"]
        report = {"kind": "jfg-generated-instruction-effects", "complete": True, "passed": True,
                  "cases": 12, "rejected": rejected, "sanitizers": ["address", "undefined"],
                  "disabled_output_unchanged": True, "hook_text_only": True,
                  "game_retirement_qualified": False, "parity_verified": False,
                  "inputs": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                  "commands": receipts}
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        return report
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        (output / "failure.json").write_text(json.dumps({"complete": False, "error": str(error), "commands": receipts}, indent=2) + "\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    for name in ("recompiler", "control-recompiler", "include"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = run(args.output, args.recompiler, args.control_recompiler, args.include)
    print(json.dumps({key: value for key, value in report.items() if key not in ("inputs", "commands")}))
