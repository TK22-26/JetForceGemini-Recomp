#!/usr/bin/env python3
"""Run the private CVT.W.S micro-ROM in two isolated BizHawk N64 cores."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess

from scripts.autonomy.process_guard import WorkerJob
from scripts.phase95_bridge import digest, isolate_n64_bindings, runtime_digest
from scripts.phase95_oracle_replay import diagnostic_n64_variant


ROOT = Path(__file__).resolve().parents[1]
RESULT_HEADER = ("status", "frame", "operand_bits", "converted_word",
                 "fcr31", "marker")


def parse_trace(path: Path) -> dict:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if tuple(reader.fieldnames or ()) != RESULT_HEADER:
            raise ValueError("CPU microtest trace header changed")
        rows = list(reader)
    if len(rows) != 1 or set(rows[0]) != set(RESULT_HEADER) or \
            any(value is None for value in rows[0].values()):
        raise ValueError("CPU microtest did not write one complete result")
    row = rows[0]
    if row["status"] != "complete" or \
            not 1 <= int(row["frame"]) <= 180 or \
            int(row["operand_bits"], 16) != 0x440BA000 or \
            int(row["marker"], 16) != 0x4A464743:
        raise ValueError("CPU microtest did not reach the expected payload")
    converted = int(row["converted_word"], 16)
    fcr31 = int(row["fcr31"], 16)
    if not 0 <= converted <= 0xFFFFFFFF or fcr31 & 3:
        raise ValueError("CPU microtest did not retain rounding mode zero")
    return {"frame": int(row["frame"]),
            "operand_bits": row["operand_bits"],
            "converted_word": row["converted_word"],
            "converted_integer": converted,
            "fcr31": row["fcr31"],
            "rounding_mode": fcr31 & 3,
            "matches_vr4300_manual": converted == 558}


def run(output: Path, emulator: Path, rom: Path, rom_sha256: str,
        core: str, timeout: int = 180, *, probe: str = "rounding",
        mupen_cpu_core: int | None = None) -> dict:
    if probe not in ("rounding", "clock", "queue", "queue_threads", "translation", "cache", "mask", "rsp", "vi", "branch", "links", "eret", "interrupt", "dma", "vi_manager", "boot_state", "vi_phase", "pi_timing", "compare", "si_overlap", "flash", "ai"):
        raise ValueError("unsupported CPU probe")
    output = output.resolve()
    emulator = emulator.resolve(strict=True)
    rom = rom.resolve(strict=True)
    private = (ROOT / "tools" / "private").resolve(strict=True)
    if not output.is_relative_to(private) or output.exists():
        raise ValueError("CPU microtest output must be a new private directory")
    if core not in ("Mupen64Plus", "Ares64"):
        raise ValueError("unsupported N64 CPU test core")
    if mupen_cpu_core is not None and (core != "Mupen64Plus" or
            type(mupen_cpu_core) is not int or mupen_cpu_core not in (0, 1, 2)):
        raise ValueError("CPU override requires an explicit Mupen interpreter/dynarec")
    if type(timeout) is not int or not 30 <= timeout <= 600:
        raise ValueError("CPU microtest timeout must be 30..600 seconds")
    expected_size = (32 if probe == 'boot_state' else 2) * 1024 * 1024
    if probe == 'boot_state' and rom_sha256 != '159dde164c475976a3e527fbb20978431d4765f2c63019b3530c3aa8772595aa':
        raise ValueError('hardware startup capture requires the pinned original ROM')
    if rom.stat().st_size != expected_size or digest(rom) != rom_sha256:
        raise ValueError("private CPU test ROM identity mismatch")
    output.mkdir(parents=True)
    isolated = output / "emulator"
    shutil.copytree(emulator.parent, isolated,
                    ignore=shutil.ignore_patterns("SaveRAM", "State", "States"))
    config = isolated / "config.ini"
    settings = json.loads(config.read_text(encoding="utf-8-sig"))
    for entry in settings.get("PathEntries", {}).get("Paths", []):
        configured = Path(entry.get("Path", ""))
        if configured.is_absolute() or ".." in configured.parts:
            raise ValueError("absolute emulator data path is not isolated")
    settings = diagnostic_n64_variant(
        isolate_n64_bindings(settings),
        "Ares64" if core == "Ares64" else None, mupen_cpu_core)
    config.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    # EmuHawk rewrites config.ini on exit (UI/recent-file state). Retain the
    # exact launch bytes separately so later qualification never substitutes
    # that post-run configuration for the configuration actually requested.
    input_config = output / "input-config.json"
    shutil.copyfile(config, input_config)
    script = Path(__file__).with_name(f"phase9_cpu_{probe}_probe.lua")
    manifest = {"kind": f"jfg-phase9-cpu-{probe}-microtest", "schema": 1,
                "acceptance": False, "core": core, "rom_sha256": rom_sha256,
                "emulator_sha256": digest(isolated / emulator.name),
                "runtime_sha256": runtime_digest(isolated),
                "config_sha256": digest(config), "script_sha256": digest(script),
                "input_config_sha256": digest(input_config),
                "source_rom_bootcode": "unmodified private original ROM" if probe == 'boot_state' else "private local derivative; not redistributed",
                "retains_original_static_code": probe in ("queue", "queue_threads", "translation", "cache", "mask", "rsp", "interrupt", "vi_manager", "boot_state")}
    if mupen_cpu_core is not None:
        manifest["mupen_cpu_core_override"] = mupen_cpu_core
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    environment = os.environ.copy()
    environment["JFG_CPU_MICRO_ROOT"] = str(output)
    with (output / "stdout.log").open("wb") as stdout, \
            (output / "stderr.log").open("wb") as stderr, \
            WorkerJob(memory_limit_bytes=8 * 1024 * 1024 * 1024,
                      cpu_seconds=timeout) as guard:
        process = subprocess.Popen(
            [str(isolated / emulator.name), str(rom), f"--lua={script}"],
            cwd=isolated, env=environment, stdout=stdout, stderr=stderr,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            guard.assign(process)
            (output / "process.json").write_text(json.dumps({"pid": process.pid}) + "\n")
            exit_code = process.wait(timeout=timeout)
        except BaseException:
            guard.close()
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=30)
            raise
    trace = output / f"cpu-{probe}.tsv"
    parser = parse_trace
    if probe == "links":
        from scripts.phase9_cpu_links_trace import parse_trace as parser
    elif probe == "ai":
        from scripts.phase9_cpu_ai_trace import parse_trace as parser
    elif probe == "flash":
        from scripts.phase9_cpu_flash_trace import parse_trace as parser
    elif probe == "si_overlap":
        from scripts.phase9_cpu_si_overlap_trace import parse_trace as parser
    elif probe == "compare":
        from scripts.phase9_cpu_compare_trace import parse_trace as parser
    elif probe == "pi_timing":
        from scripts.phase9_cpu_pi_timing_trace import parse_trace as parser
    elif probe == "vi_phase":
        from scripts.phase9_cpu_vi_phase_trace import parse_trace as parser
    elif probe == "boot_state":
        from scripts.phase9_cpu_boot_state_trace import parse_trace as parser
    elif probe == "vi_manager":
        from scripts.phase9_cpu_vi_manager_trace import parse_trace as parser
    elif probe == "dma":
        from scripts.phase9_cpu_dma_trace import parse_trace as parser
    elif probe == "clock":
        from scripts.phase9_cpu_clock_trace import parse_trace as parser
    elif probe == "queue":
        from scripts.phase9_cpu_queue_trace import parse_trace as parser
    elif probe == "queue_threads":
        from scripts.phase9_cpu_queue_threads_trace import parse_trace as parser
    elif probe == "translation":
        from scripts.phase9_cpu_translation_trace import parse_trace as parser
    elif probe == "cache":
        from scripts.phase9_cpu_cache_trace import parse_trace as parser
    elif probe == "mask":
        from scripts.phase9_cpu_mask_trace import parse_trace as parser
    elif probe == "rsp":
        from scripts.phase9_cpu_rsp_trace import parse_trace as parser
    elif probe == "vi":
        from scripts.phase9_cpu_vi_trace import parse_trace as parser
    elif probe == "branch":
        from scripts.phase9_cpu_branch_trace import parse_trace as parser
    elif probe == "eret":
        from scripts.phase9_cpu_eret_trace import parse_trace as parser
    elif probe == "interrupt":
        from scripts.phase9_cpu_interrupt_trace import parse_trace as parser
    try:
        observed = parser(trace) if trace.is_file() else None
    except (OSError, ValueError, TypeError) as error:
        observed = {"trace_error": str(error)}
    result = {**manifest, "exit_code": exit_code,
              "trace_sha256": digest(trace) if trace.is_file() else None,
              "observed": observed,
              "complete": exit_code == 0 and observed is not None and
                          "trace_error" not in observed}
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    if not result["complete"]:
        raise RuntimeError(f"CPU microtest failed closed: {output}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--core", choices=("Mupen64Plus", "Ares64"), required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--mupen-cpu-core", type=int, choices=(0, 1, 2))
    parser.add_argument("--probe", choices=("rounding", "clock", "queue", "queue_threads", "translation", "cache", "mask", "rsp", "vi", "branch", "links", "eret", "interrupt", "dma", "vi_manager", "boot_state", "vi_phase", "pi_timing", "compare", "si_overlap", "flash", "ai"), default="rounding")
    args = parser.parse_args()
    result = run(args.output, args.emulator, args.rom, args.rom_sha256,
                 args.core, args.timeout, probe=args.probe, mupen_cpu_core=args.mupen_cpu_core)
    print(json.dumps({"core": result["core"], "observed": result["observed"],
                      "output": str(args.output)}))


if __name__ == "__main__":
    main()
