"""Replay an exported selected-poll route in a fresh isolated BizHawk worker."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from scripts import phase9_point_probe as point_probe
from scripts import phase9_device_events as device_event_probe
from scripts import phase9_oracle_cpu_boundaries as cpu_boundaries
from scripts import phase9_oracle_instruction_effects as instruction_effects

from scripts.phase95_bridge import digest, isolate_n64_bindings, runtime_digest
from scripts.autonomy.process_guard import WorkerJob
from scripts.compare_phase9_retrace_hashes import iter_trace
from scripts.compare_phase9_update_hashes import records as update_records
from scripts.compare_phase9_poll_hashes import records as poll_records
from scripts.prepare_phase9_oracle_flash import inspect_mupen_saveram
from scripts.phase9_event_trace import read as read_event_trace, spec as event_spec, validate_windows
from scripts.phase9_update_word import read as read_update_word, validate_update_word
from scripts.phase9_controller_return import read as read_controller_return
from scripts.phase9_controller_callers import read as read_controller_callers
from scripts.phase9_si_trace import read as read_si_trace


def select_target(export_target: int, requested: int | None) -> int:
    if type(export_target) is not int or not 3 <= export_target <= 1_000_000:
        raise ValueError("invalid oracle replay target")
    if requested is None:
        return export_target
    if type(requested) is not int or not 3 <= requested <= export_target:
        raise ValueError("diagnostic target exceeds exported route")
    return requested


def validate_focus(focus_updates, update_hashes):
    if focus_updates is None:
        return None
    if (not update_hashes or not isinstance(focus_updates, (tuple, list)) or
            len(focus_updates) != 2 or
            any(type(value) is not int for value in focus_updates) or
            not 1 <= focus_updates[0] <= focus_updates[1] or
            focus_updates[1] - focus_updates[0] > 15):
        raise ValueError("focused update capture requires 1..16 hashed updates")
    return tuple(focus_updates)


def validate_watch_word(watch_word, focus, vi_trace):
    if watch_word is None:
        return None
    if (type(watch_word) is not int or focus is None or not vi_trace or
            not 0x80000000 <= watch_word <= 0x803FFFFC or
            watch_word % 4 != 0):
        raise ValueError("actor-word watch requires focused VI tracing and a KSEG0 word")
    return watch_word


def validate_entry_pc(entry_pc, focus, vi_trace):
    if entry_pc is None:
        return None
    if (type(entry_pc) is not int or focus is None or not vi_trace or
            not 0x80000000 <= entry_pc <= 0x803FFFFC or entry_pc % 4 != 0):
        raise ValueError("entry probe requires focused VI tracing and a KSEG0 PC")
    return entry_pc


def validate_entry_register_catalog(enabled, entry_pc):
    if type(enabled) is not bool or (enabled and entry_pc is None):
        raise ValueError("register catalog requires a focused entry probe")
    return enabled


def validate_entry_fpu(enabled, entry_pc):
    if type(enabled) is not bool or (enabled and entry_pc is None):
        raise ValueError("entry FPU trace requires a focused entry probe")
    return enabled


def validate_entry_memory(enabled, entry_pc):
    if type(enabled) is not bool or (enabled and entry_pc is None):
        raise ValueError("entry memory trace requires a focused entry probe")
    return enabled


def validate_entry_gpr(enabled, entry_pc):
    if type(enabled) is not bool or (enabled and entry_pc is None):
        raise ValueError("entry GPR trace requires a focused entry probe")
    return enabled


def validate_entry_fcr(enabled, entry_pc):
    if type(enabled) is not bool or (enabled and entry_pc is None):
        raise ValueError("entry FCR trace requires a focused entry probe")
    return enabled


def diagnostic_n64_variant(settings: dict, preferred_core: str | None,
                           mupen_cpu_core: int | None) -> dict:
    """Change only an isolated diagnostic config; never the installed profile."""
    if preferred_core is None and mupen_cpu_core is None:
        return settings
    if preferred_core not in (None, "Ares64"):
        raise ValueError("diagnostic N64 core must be Ares64 or the pinned default")
    if preferred_core == "Ares64" and mupen_cpu_core is not None:
        raise ValueError("Ares64 cannot use a Mupen CPU override")
    if settings.get("PreferredCores", {}).get("N64") != "Mupen64Plus":
        raise ValueError("diagnostic override requires pinned Mupen64Plus default")
    isolated = json.loads(json.dumps(settings))
    if preferred_core == "Ares64":
        isolated["PreferredCores"]["N64"] = "Ares64"
        return isolated
    override = mupen_cpu_core
    if type(override) is not int or override not in (0, 1, 2):
        raise ValueError("Mupen CPU override must be pure(0), cached(1), or dynarec(2)")
    key = "BizHawk.Emulation.Cores.Nintendo.N64.N64"
    sync = isolated.get("CoreSyncSettings", {}).get(key)
    if not isinstance(sync, dict) or type(sync.get("Core")) is not int or \
            sync["Core"] not in (0, 1, 2):
        raise ValueError("installed Mupen CPU setting is unavailable")
    isolated["CoreSyncSettings"][key]["Core"] = override
    return isolated


def validate_queue_trace(queues, focus, vi_trace):
    if not queues:
        return ()
    if (focus is None or not vi_trace or len(queues) > 8 or
            any(type(queue) is not int or not 0x80000000 <= queue <= 0x803FFFFC
                or queue % 4 != 0 for queue in queues) or
            len(set(queues)) != len(queues)):
        raise ValueError("queue probe requires focused VI tracing and 1..8 distinct KSEG0 queues")
    return tuple(sorted(queues))


def parse_domain_inventory(lines: list[str]) -> list[dict]:
    rows = [line.split("\t") for line in lines
            if line.startswith("memory-domain\t")]
    if not 1 <= len(rows) <= 64:
        raise ValueError("oracle memory-domain inventory is missing or unbounded")
    domains = []
    for row in rows:
        if (len(row) != 3 or not row[1] or row[1].strip() != row[1] or
                not row[2].isdecimal() or int(row[2]) <= 0):
            raise ValueError("oracle memory-domain inventory is invalid")
        domains.append({"name": row[1], "size": int(row[2])})
    if len({row["name"] for row in domains}) != len(domains) or \
            domains != sorted(domains, key=lambda row: row["name"]):
        raise ValueError("oracle memory-domain inventory is not unique and sorted")
    return domains


def replay(output, emulator, rom, rom_sha256, source, *, checkpoints=(),
           timeout=1800, target_frame=None, vi_trace=False,
           update_hashes=False, poll_hashes=False, focus_updates=None, watch_word=None,
           update_word=None,
           entry_pc=None, queue_trace=(), entry_register_catalog=False,
           entry_fpu=False, entry_memory=False, entry_gpr=False,
           entry_fcr=False, mupen_cpu_core=None, preferred_n64_core=None,
           domain_inventory=False, event_windows=(),
           controller_return_pc=None, si_trace=False, si_clock_trace=False,
           queue_clock_trace=False, point_pcs=(), point_words=(), device_events=False,
           cpu_boundary_update=None, instruction_effect_update=None):
    if type(queue_clock_trace) is not bool or (queue_clock_trace and not queue_trace):
        raise ValueError("queue clock trace requires queue tracing")
    if type(si_clock_trace) is not bool or (si_clock_trace and not si_trace):
        raise ValueError("SI clock trace requires SI transaction tracing")
    output, emulator, rom, source = map(lambda value: Path(value).resolve(),
                                        (output, emulator, rom, source))
    if output.exists():
        raise FileExistsError(output)
    if digest(rom) != rom_sha256:
        raise ValueError("ROM identity mismatch")
    source_manifest = json.loads((source / "export-manifest.json").read_text())
    replay_file = source / "controller.input"
    if (source_manifest.get("kind") != "jfg-phase95-selected-input-export" or
            source_manifest.get("input_sha256") != digest(replay_file) or
            source_manifest.get("native_mode") != "replay-by-poll"):
        raise ValueError("selected input export is not pinned")
    target = select_target(source_manifest.get("oracle_final_frame"), target_frame)
    focus = validate_focus(focus_updates, update_hashes)
    point_pcs, point_words = point_probe.validate(point_pcs, point_words, focus, vi_trace)
    device_spec = device_event_probe.specification(device_events, point_pcs, focus,
        side="oracle", qualified_engine=mupen_cpu_core in (0, 1) and preferred_n64_core is None)
    cpu_spec = cpu_boundaries.specification(cpu_boundary_update, device_spec, mupen_cpu_core)
    effect_spec = instruction_effects.specification(instruction_effect_update, cpu_spec)
    watch = validate_watch_word(watch_word, focus, vi_trace)
    word = validate_update_word(update_word, update_hashes)
    entry = validate_entry_pc(entry_pc, focus, vi_trace)
    catalog = validate_entry_register_catalog(entry_register_catalog, entry)
    fpu = validate_entry_fpu(entry_fpu, entry)
    memory = validate_entry_memory(entry_memory, entry)
    gpr = validate_entry_gpr(entry_gpr, entry)
    fcr = validate_entry_fcr(entry_fcr, entry)
    queues = validate_queue_trace(queue_trace, focus, vi_trace)
    if type(poll_hashes) is not bool:
        raise ValueError("poll_hashes must be a boolean")
    event_windows = validate_windows(event_windows, poll_hashes=poll_hashes,
                                     update_hashes=update_hashes, vi_trace=vi_trace)
    if controller_return_pc is not None and (
            type(controller_return_pc) is not int or not event_windows or
            not 0x80000000 <= controller_return_pc <= 0x803FFFFC or
            controller_return_pc % 4):
        raise ValueError("controller return PC requires bounded event windows")
    if type(domain_inventory) is not bool:
        raise ValueError("domain_inventory must be a boolean")
    if (type(si_trace) is not bool or
            (si_trace and (focus is None or not vi_trace or
                           not update_hashes or not domain_inventory))):
        raise ValueError("SI trace needs focused update, VI and save inventory")
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("invalid oracle timeout")
    checkpoints = tuple(sorted(set((*checkpoints, target))))
    if any(type(value) is not int or not 3 <= value <= target for value in checkpoints):
        raise ValueError("invalid oracle checkpoint")
    output.mkdir(parents=True)
    isolated = output / "emulator"
    shutil.copytree(emulator.parent, isolated,
                    ignore=shutil.ignore_patterns("SaveRAM", "State", "States"))
    config = isolated / "config.ini"
    settings = json.loads(config.read_text(encoding="utf-8-sig"))
    for path_entry in settings.get("PathEntries", {}).get("Paths", []):
        configured = Path(path_entry.get("Path", ""))
        if configured.is_absolute() or ".." in configured.parts:
            raise ValueError("absolute emulator data path is not isolated")
    isolated_settings = diagnostic_n64_variant(
        isolate_n64_bindings(settings), preferred_n64_core, mupen_cpu_core)
    uses_mupen = isolated_settings.get("PreferredCores", {}).get("N64") == "Mupen64Plus"
    config.write_text(json.dumps(isolated_settings, indent=2) + "\n",
                      encoding="utf-8")
    script = Path(__file__).with_name("phase9_bizhawk_oracle.lua")
    manifest = {"kind": "jfg-phase95-oracle-poll-replay", "schema": 1,
                "acceptance": False, "source_export": str(source),
                "source_export_sha256": digest(source / "export-manifest.json"),
                "input_sha256": digest(replay_file), "target_frame": target,
                "checkpoints": checkpoints, "input_clock": "controller-poll",
                "vi_consumed_trace": bool(vi_trace),
                "completed_update_trace": bool(update_hashes),
                "poll_semantic_hashes": poll_hashes,
                "event_windows": event_windows,
                "domain_inventory": domain_inventory,
                "si_trace": si_trace,
                "si_clock_trace": si_clock_trace,
                "focused_update_range": focus,
                "watch_word": f"0x{watch:08x}" if watch is not None else None,
                "update_word": f"0x{word:08x}" if word is not None else None,
                "controller_return_pc": f"0x{controller_return_pc:08x}"
                if controller_return_pc is not None else None,
                "entry_pc": f"0x{entry:08x}" if entry is not None else None,
                "entry_register_catalog": catalog,
                "entry_fpu": fpu,
                "entry_memory": memory,
                "entry_gpr": gpr,
                "entry_fcr": fcr,
                "mupen_cpu_core_override": mupen_cpu_core,
                "preferred_n64_core_override": preferred_n64_core,
                "queue_trace": [f"0x{queue:08x}" for queue in queues],
                "queue_clock_trace": queue_clock_trace,
                "rom_sha256": rom_sha256,
                "emulator_sha256": digest(isolated / emulator.name),
                "config_sha256": digest(config), "runtime_sha256": runtime_digest(isolated),
                "script_sha256": digest(script), "initial_save": "fresh isolated worker"}
    if point_pcs:
        manifest["point_probe"] = {"pcs": list(point_pcs), "words": list(point_words), "phase": point_probe.PHASE}
    if device_spec is not None:
        manifest["device_events"] = device_spec
    if cpu_spec is not None:
        manifest["cpu_boundaries"] = cpu_spec
    if effect_spec is not None:
        manifest["instruction_effects"] = effect_spec
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    environment = os.environ.copy()
    cpu_boundaries.configure(environment, cpu_spec)
    instruction_effects.configure(environment, effect_spec)
    environment.pop("JFG_PHASE9_DEVICE_EVENTS", None)
    if device_events:
        environment["JFG_PHASE9_DEVICE_EVENTS"] = "1"
    environment.update(JFG_PHASE9_ORACLE_ROOT=str(output),
                       JFG_PHASE9_REPLAY_PATH=str(replay_file),
                       JFG_PHASE9_ORACLE_TARGET=str(target),
                       JFG_PHASE9_ORACLE_CHECKPOINTS=",".join(map(str, checkpoints)),
                       JFG_PHASE9_ORACLE_INPUT_CLOCK="controller-poll")
    if vi_trace:
        environment["JFG_PHASE9_ORACLE_VI_TRACE"] = "1"
    else:
        environment.pop("JFG_PHASE9_ORACLE_VI_TRACE", None)
    if update_hashes:
        environment["JFG_PHASE9_UPDATE_HASHES"] = "1"
    else:
        environment.pop("JFG_PHASE9_UPDATE_HASHES", None)
    if poll_hashes:
        environment["JFG_PHASE9_POLL_HASHES"] = "1"
    else:
        environment.pop("JFG_PHASE9_POLL_HASHES", None)
    if event_windows:
        environment["JFG_PHASE9_EVENT_TRACE_RANGE"] = event_spec(event_windows)
    else:
        environment.pop("JFG_PHASE9_EVENT_TRACE_RANGE", None)
    if controller_return_pc is not None:
        environment["JFG_PHASE9_CONTROLLER_RETURN_PC"] = \
            f"0x{controller_return_pc:08x}"
    else:
        environment.pop("JFG_PHASE9_CONTROLLER_RETURN_PC", None)
    if si_trace:
        environment["JFG_PHASE9_SI_TRACE"] = "1"
    else:
        environment.pop("JFG_PHASE9_SI_TRACE", None)
    if si_clock_trace:
        environment["JFG_PHASE9_SI_CLOCK_TRACE"] = "1"
    else:
        environment.pop("JFG_PHASE9_SI_CLOCK_TRACE", None)
    if domain_inventory:
        environment["JFG_PHASE9_ORACLE_DOMAIN_INVENTORY"] = "1"
    else:
        environment.pop("JFG_PHASE9_ORACLE_DOMAIN_INVENTORY", None)
    if focus is not None:
        environment["JFG_PHASE9_FOCUS_UPDATES"] = f"{focus[0]}:{focus[1]}"
    else:
        environment.pop("JFG_PHASE9_FOCUS_UPDATES", None)
    if watch is not None:
        environment["JFG_PHASE9_WATCH_WORD"] = f"0x{watch:08x}"
    else:
        environment.pop("JFG_PHASE9_WATCH_WORD", None)
    if word is not None:
        environment["JFG_PHASE9_UPDATE_WORD"] = f"0x{word:08x}"
    else:
        environment.pop("JFG_PHASE9_UPDATE_WORD", None)
    if entry is not None:
        environment["JFG_PHASE9_ENTRY_PC"] = f"0x{entry:08x}"
    else:
        environment.pop("JFG_PHASE9_ENTRY_PC", None)
    if catalog:
        environment["JFG_PHASE9_ENTRY_REGISTER_CATALOG"] = "1"
    else:
        environment.pop("JFG_PHASE9_ENTRY_REGISTER_CATALOG", None)
    if fpu:
        environment["JFG_PHASE9_ENTRY_FPU"] = "1"
    else:
        environment.pop("JFG_PHASE9_ENTRY_FPU", None)
    if memory:
        environment["JFG_PHASE9_ENTRY_MEMORY"] = "1"
    else:
        environment.pop("JFG_PHASE9_ENTRY_MEMORY", None)
    if gpr:
        environment["JFG_PHASE9_ENTRY_GPR"] = "1"
    else:
        environment.pop("JFG_PHASE9_ENTRY_GPR", None)
    if fcr:
        environment["JFG_PHASE9_ENTRY_FCR"] = "1"
    else:
        environment.pop("JFG_PHASE9_ENTRY_FCR", None)
    if queues:
        environment["JFG_PHASE9_QUEUE_TRACE"] = ",".join(
            f"0x{queue:08x}" for queue in queues)
    else:
        environment.pop("JFG_PHASE9_QUEUE_TRACE", None)
    environment.pop("JFG_PHASE9_QUEUE_CLOCK_TRACE", None)
    if queue_clock_trace:
        environment["JFG_PHASE9_QUEUE_CLOCK_TRACE"] = "1"
    for name, values in (("JFG_PHASE9_POINT_PCS", point_pcs), ("JFG_PHASE9_POINT_WORDS", point_words)):
        environment.pop(name, None)
        if values:
            environment[name] = point_probe.specification(values)
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
        except subprocess.TimeoutExpired as error:
            guard.close()
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=30)
            raise TimeoutError("owned oracle replay exceeded declared wall-time budget") from error
        except BaseException:
            guard.close()
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=30)
            raise
    trace = output / "checkpoints.tsv"
    lines = trace.read_text().splitlines() if trace.exists() else []
    try:
        domains = parse_domain_inventory(lines) if domain_inventory else None
    except ValueError:
        domains = None
    saveram_regions = None
    if domain_inventory and uses_mupen:
        saveram_path = isolated / "N64" / "SaveRAM" / (rom.stem + ".SaveRAM")
        if saveram_path.is_file():
            try:
                saveram_regions = inspect_mupen_saveram(saveram_path.read_bytes())
            except ValueError:
                pass
    initial_hashes = [line.split("\t", 1)[1] for line in lines
                      if line.startswith("initial-flash-sha256\t")]
    expected_flash = (source_manifest.get("initial_state") or {}).get("flash_sha256")
    initial_flash_match = (len(initial_hashes) == 1 and
                           (expected_flash is None or initial_hashes[0] == expected_flash))
    consumed_path = output / "consumed-vi-hashes.jsonl"
    consumed_count = sum(1 for _ in iter_trace(consumed_path)) if \
        vi_trace and consumed_path.is_file() else 0
    update_path = output / "update-hashes.jsonl"
    update_count = sum(1 for _ in update_records(update_path)) if \
        update_hashes and update_path.is_file() else 0
    word_path = output / "update-word.tsv"
    try:
        word_count = len(read_update_word(word_path, word)) if \
            word is not None else None
    except (OSError, ValueError):
        word_count = None
    word_complete = (word_count == update_count and word_count > 0) if \
        word is not None and word_count is not None else None
    poll_hash_path = output / "poll-hashes.jsonl"
    poll_hash_count = sum(1 for _ in poll_records(poll_hash_path, "oracle")) if \
        poll_hashes and poll_hash_path.is_file() else 0
    try:
        event_count = len(read_event_trace(output / "events.tsv", event_windows,
                                           "oracle")) if event_windows else None
    except (OSError, ValueError):
        event_count = None
    caller_path = output / "controller-callers.tsv"
    try:
        caller_count = len(read_controller_callers(caller_path, event_windows)) \
            if event_windows else None
    except (OSError, ValueError):
        caller_count = None
    controller_return_path = output / "controller-return.tsv"
    try:
        controller_return_count = len(read_controller_return(
            controller_return_path, tuple(event_windows))) if \
            controller_return_pc is not None else None
    except (OSError, ValueError):
        controller_return_count = None
    si_path = output / "si-transactions.tsv"
    try:
        si_count = len(read_si_trace(si_path, tuple(focus))) if si_trace else None
    except (OSError, ValueError):
        si_count = None
    observed_input_polls = sum(line.startswith("input-poll\t") for line in lines)
    focus_complete = (all((output / f"focus-update-{index}.rdram").is_file() and
                          (output / f"focus-update-{index}.rdram").stat().st_size ==
                          4 * 1024 * 1024
                          for index in range(focus[0], focus[1] + 1))
                      if focus is not None else None)
    watch_lines = (output / "watch-word.tsv").read_text(encoding="utf-8").splitlines() \
        if watch is not None and (output / "watch-word.tsv").is_file() else []
    watch_complete = (len(watch_lines) >= 2 and
                      watch_lines[0].startswith("address\tframe\t") and
                      watch_lines[-1].startswith("result\ttrue\t") and
                      len(watch_lines) <= 1026) if watch is not None else None
    watch_hits = len(watch_lines) - 2 if watch_complete else None
    if watch_complete and watch_lines[-1] != f"result\ttrue\t{watch_hits}":
        watch_complete = False
    entry_lines = (output / "entry-args.tsv").read_text(encoding="utf-8").splitlines() \
        if entry is not None and (output / "entry-args.tsv").is_file() else []
    entry_complete = (len(entry_lines) >= 3 and
                      entry_lines[0].startswith("frame\tcompleted_updates\t") and
                      entry_lines[-1].startswith("result\ttrue\t") and
                      len(entry_lines) <= 1026) if entry is not None else None
    entry_hits = len(entry_lines) - 2 if entry_complete else None
    if entry_complete and entry_lines[-1] != f"result\ttrue\t{entry_hits}":
        entry_complete = False
    fpu_lines = (output / "entry-fpu.tsv").read_text(encoding="utf-8").splitlines() \
        if fpu and (output / "entry-fpu.tsv").is_file() else []
    fpu_header = ("frame", "completed_updates", "controller_polls",
                  "consumed_vi", "pc", *(field for index in range(32)
                  for field in (f"f{index}_lo", f"f{index}_hi")))
    fpu_complete = (entry_complete and len(fpu_lines) == len(entry_lines) and
                    tuple(fpu_lines[0].split("\t")) == fpu_header and
                    fpu_lines[-1] == f"result\ttrue\t{entry_hits}" and
                    all(len(line.split("\t")) == len(fpu_header) for line in
                        fpu_lines[1:-1])) if fpu else None
    memory_lines = (output / "entry-memory.tsv").read_text(
        encoding="utf-8").splitlines() if memory and (
            output / "entry-memory.tsv").is_file() else []
    memory_header = ("frame", "completed_updates", "controller_polls",
                     "consumed_vi", "pc", "a1_256", "a2_256", "a3_256")
    memory_complete = (entry_complete and
                       len(memory_lines) == len(entry_lines) and
                       tuple(memory_lines[0].split("\t")) == memory_header and
                       memory_lines[-1] == f"result\ttrue\t{entry_hits}" and
                       all(len(line.split("\t")) == len(memory_header) and
                           all(len(word) == 512 for word in line.split("\t")[5:])
                           for line in memory_lines[1:-1])) if memory else None
    gpr_lines = (output / "entry-gpr.tsv").read_text(
        encoding="utf-8").splitlines() if gpr and (
            output / "entry-gpr.tsv").is_file() else []
    gpr_header = ("frame", "completed_updates", "controller_polls",
                  "consumed_vi", "pc", *(field for index in range(32)
                  for field in (f"r{index}_lo", f"r{index}_hi")))
    gpr_complete = (entry_complete and len(gpr_lines) == len(entry_lines) and
                    tuple(gpr_lines[0].split("\t")) == gpr_header and
                    gpr_lines[-1] == f"result\ttrue\t{entry_hits}" and
                    all(len(line.split("\t")) == len(gpr_header) for line in
                        gpr_lines[1:-1])) if gpr else None
    fcr_lines = (output / "entry-fcr.tsv").read_text(
        encoding="utf-8").splitlines() if fcr and (
            output / "entry-fcr.tsv").is_file() else []
    fcr_header = ("frame", "completed_updates", "controller_polls",
                  "consumed_vi", "pc", "fcr31")
    fcr_complete = (entry_complete and len(fcr_lines) == len(entry_lines) and
                    tuple(fcr_lines[0].split("\t")) == fcr_header and
                    fcr_lines[-1] == f"result\ttrue\t{entry_hits}" and
                    all(len(line.split("\t")) == len(fcr_header) and
                        line.split("\t")[5].startswith("0x") for line in
                        fcr_lines[1:-1])) if fcr else None
    catalog_lines = (output / "entry-register-catalog.tsv").read_text(
        encoding="utf-8").splitlines() if catalog and (
            output / "entry-register-catalog.tsv").is_file() else []
    catalog_complete = (len(catalog_lines) >= 2 and len(catalog_lines) <= 513 and
                        catalog_lines[0] == "name\ttype\tvalue" and
                        all(len(line.split("\t")) == 3 for line in
                            catalog_lines[1:])) if catalog else None
    queue_lines = (output / "queue-calls.tsv").read_text(encoding="utf-8").splitlines() \
        if queues and (output / "queue-calls.tsv").is_file() else []
    queue_complete = (len(queue_lines) >= 3 and
                      queue_lines[0].startswith("frame\tcompleted_updates\t") and
                      queue_lines[-1].startswith("result\ttrue\t") and
                      len(queue_lines) <= 4098) if queues else None
    queue_hits = len(queue_lines) - 2 if queue_complete else None
    clock_lines = (output / "queue-clock.tsv").read_text().splitlines() \
        if queue_clock_trace and (output / "queue-clock.tsv").is_file() else []
    clock_complete = (3 <= len(clock_lines) <= 8194 and
                      clock_lines[0] == "event\tframe\tupdate\tpoll\tvi\tcount\tepc\tcause" and
                      clock_lines[-1] == f"result\ttrue\t{len(clock_lines) - 2}" and
                      all(len(line.split("\t")) == 8 for line in clock_lines[1:-1])) \
        if queue_clock_trace else None
    if queue_complete and queue_lines[-1] != f"result\ttrue\t{queue_hits}":
        queue_complete = False
    os_clock_summary = None
    rcp_clock_summary = None
    if queue_clock_trace:
        from scripts.phase9_os_call_clock import summarize as summarize_os_clock
        from scripts.phase9_rcp_clock import summarize as summarize_rcp_clock
        try:
            os_clock_summary = summarize_os_clock(output / "os-call-clock.tsv")
        except (OSError, ValueError):
            pass
        try:
            rcp_clock_summary = summarize_rcp_clock(output / "rcp-clock.tsv", output / "queue-clock.tsv")
        except (OSError, ValueError):
            pass
    result = {**manifest, "exit_code": exit_code,
              "trace_complete": f"result\ttrue\t{target}" in lines,
              "vi_consumed_count": consumed_count if vi_trace else None,
              "vi_consumed_trace_complete": consumed_count > 0 if vi_trace else None,
              "completed_update_count": update_count if update_hashes else None,
              "completed_update_trace_complete": update_count > 0 if update_hashes else None,
              "update_word_trace_complete": word_complete,
              "update_word_trace_sha256": digest(word_path)
              if word_complete else None,
              "poll_semantic_hash_count": poll_hash_count if poll_hashes else None,
              "event_trace_rows": event_count,
              "event_trace_complete": event_count is not None
              if event_windows else None,
              "controller_caller_rows": caller_count,
              "controller_caller_trace_complete": caller_count is not None
              if event_windows else None,
              "controller_caller_trace_sha256": digest(caller_path)
              if caller_count is not None else None,
              "controller_return_rows": controller_return_count,
              "controller_return_trace_complete":
                  controller_return_count is not None
                  if controller_return_pc is not None else None,
              "controller_return_trace_sha256": digest(controller_return_path)
                  if controller_return_count is not None else None,
              "si_transaction_rows": si_count,
              "si_transaction_trace_complete": si_count is not None
                  if si_trace else None,
              "si_transaction_trace_sha256": digest(si_path)
                  if si_count is not None else None,
              "poll_semantic_hash_sha256": digest(poll_hash_path)
              if poll_hashes and poll_hash_path.is_file() else None,
              "poll_semantic_hash_trace_complete": (
                  poll_hash_count > 0 and poll_hash_count == observed_input_polls
              ) if poll_hashes else None,
              "focused_update_capture_complete": focus_complete,
              "watch_word_trace_complete": watch_complete,
              "watch_word_hits": watch_hits,
              "entry_trace_complete": entry_complete,
              "entry_hits": entry_hits,
              "entry_register_catalog_complete": catalog_complete,
              "entry_fpu_trace_complete": fpu_complete,
              "entry_memory_trace_complete": memory_complete,
              "entry_gpr_trace_complete": gpr_complete,
              "entry_fcr_trace_complete": fcr_complete,
              "queue_trace_complete": queue_complete,
              "queue_hits": queue_hits,
              "queue_clock_trace_complete": clock_complete,
              "os_call_clock_summary": os_clock_summary,
              "rcp_clock_summary": rcp_clock_summary,
              "oracle_initial_flash_sha256": initial_hashes[0] if len(initial_hashes) == 1 else None,
              "initial_flash_matches_candidate": initial_flash_match,
              "memory_domains": domains,
              "mupen_saveram_regions": saveram_regions,
              "final_rdram_sha256": digest(output / f"checkpoint-{target:06d}.rdram")
              if (output / f"checkpoint-{target:06d}.rdram").exists() else None}
    if point_pcs:
        result["point_probe"] = {**manifest["point_probe"], **point_probe.summary(
            output / "point-probe.tsv", point_pcs, point_words, focus, oracle=True)}
        if result["point_probe"]["complete"]:
            result["point_probe"]["sha256"] = digest(output / "point-probe.tsv")
    if device_spec is not None:
        result["device_events"] = {**device_spec, **device_event_probe.summary(
            output / "device-events.tsv", device_spec, side="oracle")}
        if result["device_events"]["complete"]:
            result["device_events"]["sha256"] = digest(output / "device-events.tsv")
    if cpu_spec is not None:
        result["cpu_boundaries"] = {**cpu_spec, **cpu_boundaries.summary(output / "cpu-boundaries.tsv", cpu_spec)}
        if result["cpu_boundaries"]["complete"]:
            result["cpu_boundaries"]["sha256"] = digest(output / "cpu-boundaries.tsv")
    if effect_spec is not None:
        result["instruction_effects"] = {**effect_spec, **instruction_effects.summary(output / "oracle-effects.bin", effect_spec)}
        if result["instruction_effects"]["complete"]:
            result["instruction_effects"]["sha256"] = digest(output / "oracle-effects.bin")
    (output / "oracle-result.json").write_text(json.dumps(result, indent=2) + "\n")
    if (exit_code != 0 or not result["trace_complete"] or
            not initial_flash_match or result["final_rdram_sha256"] is None or
            (domain_inventory and domains is None) or
            (domain_inventory and uses_mupen and
             saveram_regions is None) or
            (vi_trace and consumed_count == 0) or
            (update_hashes and update_count == 0) or
            (word is not None and not word_complete) or
            (poll_hashes and not result["poll_semantic_hash_trace_complete"]) or
            (event_windows and not result["event_trace_complete"]) or
            (event_windows and not result["controller_caller_trace_complete"]) or
            (controller_return_pc is not None and
             controller_return_count is None) or
            (si_trace and si_count is None) or
            (focus is not None and (update_count < focus[1] or not focus_complete)) or
            (watch is not None and not watch_complete) or
            (entry is not None and not entry_complete) or
            (catalog and not catalog_complete) or
            (fpu and not fpu_complete) or
            (memory and not memory_complete) or
            (gpr and not gpr_complete) or
            (fcr and not fcr_complete) or
            (queues and not queue_complete) or
            (point_pcs and not result["point_probe"]["complete"]) or
            (device_events and not result["device_events"]["complete"]) or
            (cpu_spec is not None and not result["cpu_boundaries"]["complete"]) or
            (effect_spec is not None and not result["instruction_effects"]["complete"]) or
            (queue_clock_trace and (not clock_complete or os_clock_summary is None or
                                    rcp_clock_summary is None))):
        raise RuntimeError(f"oracle replay did not reach target: {output}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-events", action="store_true", help="observe bounded core device phases using a private instrumented interpreter")
    parser.add_argument("--cpu-boundary-update", type=int,
                        help="observe Count operations and ERET in one device-capture update; cached interpreter only")
    parser.add_argument("--instruction-effect-update", type=int,
                        help="observe paired cached-interpreter effects; requires the same CPU-boundary update")
    parser.add_argument("output", type=Path)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--checkpoint", type=int, action="append", default=[])
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--target-frame", type=int,
                        help="bounded diagnostic prefix of exported route")
    parser.add_argument("--vi-trace", action="store_true",
                        help="capture VI-consumption semantic hashes")
    parser.add_argument("--update-hashes", action="store_true",
                        help="capture hashes after completed guest updates")
    parser.add_argument("--poll-hashes", action="store_true",
                        help="capture pre-input semantic state at each controller poll")
    parser.add_argument("--event-window", action="append", default=[],
                        metavar="FIRST:LAST",
                        help="capture a bounded controller/update/VI event window")
    parser.add_argument("--domain-inventory", action="store_true",
                        help="record emulator memory-domain names and sizes at startup")
    parser.add_argument("--focus-updates", nargs=2, type=int, metavar=("FIRST", "LAST"),
                        help="capture canonical RDRAM at 1..16 completed updates")
    parser.add_argument("--watch-word", type=lambda value: int(value, 0),
                        help="trace writes to a focused KSEG0 actor word")
    parser.add_argument("--update-word", type=lambda value: int(value, 0),
                        help="capture one KSEG0 word after every completed update")
    parser.add_argument("--controller-return-pc",
                        type=lambda value: int(value, 0),
                        help="capture bounded GetReadData return bytes at caller PC")
    parser.add_argument("--si-trace", action="store_true",
                        help="capture bounded raw SI DMA PIF buffers and callers")
    parser.add_argument("--si-clock-trace", action="store_true",
                        help="observe core Count at SI entry, return, acknowledgement and game receive")
    parser.add_argument("--entry-pc", type=lambda value: int(value, 0),
                        help="trace A0-A3 at a focused KSEG0 function entry")
    parser.add_argument("--entry-register-catalog", action="store_true",
                        help="capture one bounded register-key catalog at entry")
    parser.add_argument("--entry-fpu", action="store_true",
                        help="capture raw FPU register words at focused entry")
    parser.add_argument("--entry-memory", action="store_true",
                        help="capture 256 input bytes from each A1-A3 pointer at entry")
    parser.add_argument("--entry-gpr", action="store_true",
                        help="capture raw GPR register words at focused entry")
    parser.add_argument("--entry-fcr", action="store_true",
                        help="capture FCR31 rounding/control word at focused entry")
    parser.add_argument("--mupen-cpu-core", type=int, choices=(0, 1, 2),
                        help="diagnostic isolated Mupen CPU mode: pure=0, cached=1, dynarec=2")
    parser.add_argument("--preferred-n64-core", choices=("Ares64",),
                        help="diagnostic isolated alternate N64 core")
    parser.add_argument("--queue-trace", type=lambda value: int(value, 0),
                        action="append", default=[],
                        help="trace a focused KSEG0 game message queue (repeatable)")
    parser.add_argument("--queue-clock-trace", action="store_true",
                        help="observe Count/EPC/Cause at queues, returns, exception entry and selected entry PC")
    parser.add_argument("--point-pc", action="append", default=[], type=lambda value: int(value, 0),
                        help="observe GPRs before a focused instruction (max 16)")
    parser.add_argument("--point-word", action="append", default=[], type=lambda value: int(value, 0),
                        help="read a KSEG0 word at each point (max 16)")
    args = parser.parse_args()
    try:
        event_windows = [tuple(map(int, value.split(":")))
                         for value in args.event_window]
    except ValueError as error:
        parser.error(f"invalid --event-window: {error}")
    print(json.dumps(replay(args.output, args.emulator, args.rom, args.rom_sha256,
                            args.source, checkpoints=args.checkpoint,
                            timeout=args.timeout, target_frame=args.target_frame,
                            vi_trace=args.vi_trace,
                            update_hashes=args.update_hashes,
                            poll_hashes=args.poll_hashes,
                            event_windows=event_windows,
                            domain_inventory=args.domain_inventory,
                            focus_updates=args.focus_updates,
                            watch_word=args.watch_word,
                            update_word=args.update_word,
                            controller_return_pc=args.controller_return_pc,
                            si_trace=args.si_trace,
                            si_clock_trace=args.si_clock_trace,
                            entry_pc=args.entry_pc,
                            entry_register_catalog=args.entry_register_catalog,
                            entry_fpu=args.entry_fpu,
                            entry_memory=args.entry_memory,
                            entry_gpr=args.entry_gpr,
                            entry_fcr=args.entry_fcr,
                            mupen_cpu_core=args.mupen_cpu_core,
                            preferred_n64_core=args.preferred_n64_core,
                            queue_trace=args.queue_trace,
                            queue_clock_trace=args.queue_clock_trace,
                            point_pcs=args.point_pc, point_words=args.point_word, device_events=args.device_events,
                            cpu_boundary_update=args.cpu_boundary_update,
                            instruction_effect_update=args.instruction_effect_update)))


if __name__ == "__main__":
    main()
