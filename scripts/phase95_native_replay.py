"""Run an exported selected-poll route on the native build with pinned inputs.

The optional poll stop is after the Nth controller-read HLE, before the guest
consumes that response; it is not an aligned oracle/native gameplay boundary.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from scripts.phase95_bridge import digest, runtime_digest
from scripts.phase95_oracle_replay import (
    select_target, validate_focus, validate_watch_word,
)
from scripts.autonomy.process_guard import WorkerJob
from scripts.build_phase9_route_replays import load_replay
from scripts.compare_phase9_update_hashes import records as update_records
from scripts.compare_phase9_poll_hashes import records as poll_records
from scripts.phase9_event_trace import read as read_event_trace, spec as event_spec, validate_windows
from scripts.phase9_update_word import read as read_update_word, validate_update_word
from scripts.phase9_controller_return import read as read_controller_return
from scripts import phase9_point_probe as point_probe
from scripts import phase9_device_events as device_event_probe
from scripts import phase9_eret_transfers as eret_transfer_probe
from scripts import phase9_instruction_effect_trace as instruction_effect_probe

INSTRUCTION_PROBE_PCS = (0x80074434, 0x80074440, 0x800744C8, 0x800744D4)
INSTRUCTION_PROBE_HEADER = (
    "update_candidate", "vi_retraces", "controller_polls", "pc",
    "r4", "r5", "r6", "r7", "r10", "r15", "r19", "r20", "r21",
    "r23", "r25", "f4_lo", "f22_lo", "f23_odd_lo", "host_fe_round",
)

EXECUTION_PROFILES = ("cooperative", "original-os-probe")


def replay_environment(inherited, profile):
    """Explicit profiles are independent of the launching shell's probe flags.

    None retains the legacy diagnostic interface. It is intentionally distinct
    from a named profile and must not be used as a pinned unattended setting.
    Do not mutate the supervisor's environment: it may run concurrent jobs.
    """
    if profile is None:
        return dict(inherited)
    if profile not in EXECUTION_PROFILES:
        raise ValueError("unknown native execution profile")
    environment = {key: value for key, value in inherited.items()
                   if not key.upper().startswith("JFG_PHASE")}
    if profile == "original-os-probe":
        environment.update(JFG_PHASE9_GUEST_OS_PROBE="1",
                           JFG_PHASE9_GUEST_LEAF_PROBE="1",
                           JFG_PHASE9_RENDERER_WRITEBACK_PROBE="1")
    return environment


def validate_execution_target(environment, target, stop_by_polls, *, poll_hashes=False):
    if environment.get("JFG_PHASE9_GUEST_OS_PROBE") == "1":
        if environment.get("JFG_PHASE9_GUEST_LEAF_PROBE") != "1":
            raise ValueError("original OS probe requires original guest leaves")
        if stop_by_polls or target < 4:
            raise ValueError("original OS probe requires a VI target of at least 4")
        # This observer lives in the cooperative controller HLE, which original
        # OS execution deliberately does not call. Never launch a capture that
        # can only produce a header-only stream, or silently discard the request.
        if poll_hashes:
            raise ValueError("original OS probe does not implement poll semantic hashes; "
                             "completed-update hashes and delivered-input tracing remain available")


def poll_completion(declared, observed):
    """Input completion is independent of a numerically equal retrace target."""
    if (type(declared) is not int or declared < 1 or
            type(observed) is not int or observed < 0):
        raise ValueError("invalid controller poll count")
    return {"input_route_complete": observed >= declared,
            "observed_controller_polls": observed,
            "missing_controller_polls": max(0, declared - observed),
            "post_eof_neutral_polls": max(0, observed - declared)}


def trace_record_count(reader, path, *args):
    """Preserve failure reports when a trapped run leaves an invalid trace.

    Never count a valid-looking prefix of a malformed stream as complete.
    The caller still rejects the run after archiving the parse error.
    """
    try:
        return sum(1 for _ in reader(path, *args)), None
    except (OSError, ValueError) as error:
        return 0, str(error)


def validate_entry_target(entry_target, focus):
    if entry_target is None:
        return None
    if (type(entry_target) is not int or focus is None or
            not 0 < entry_target <= 0xFFFFFFFF or entry_target % 4 != 0):
        raise ValueError("entry probe requires focused updates and an aligned target")
    return entry_target


def validate_entry_fpu(enabled, entry_target):
    if type(enabled) is not bool or (enabled and entry_target is None):
        raise ValueError("entry FPU trace requires a focused entry probe")
    return enabled


def validate_entry_memory(enabled, entry_target):
    if type(enabled) is not bool or (enabled and entry_target is None):
        raise ValueError("entry memory trace requires a focused entry probe")
    return enabled


def validate_entry_gpr(enabled, entry_target):
    if type(enabled) is not bool or (enabled and entry_target is None):
        raise ValueError("entry GPR trace requires a focused entry probe")
    return enabled


def validate_instruction_probe(enabled, focus):
    if type(enabled) is not bool or (enabled and focus is None):
        raise ValueError("instruction probe requires focused updates")
    return enabled


def replay(source, output, executable, rom, rom_sha256, *, timeout=1800,
           poll_trace=False, stop_by_polls=False, target_retraces=None,
           update_hashes=False, poll_hashes=False, focus_updates=None, watch_word=None,
           update_word=None,
           entry_target=None, entry_fpu=False, entry_memory=False,
           entry_gpr=False, instruction_probe=False, event_windows=(),
           controller_return=False, execution_profile=None, point_pcs=(), point_words=(), device_events=False,
           eret_transfers=False, instruction_effect_update=None):
    environment = replay_environment(os.environ, execution_profile)
    if (environment.get("JFG_PHASE9_SI_COUNT_PROBE") == "1" and
            environment.get("JFG_PHASE9_CONTROLLER_GUEST_INIT") != "1"):
        raise ValueError("SI Count probe requires original controller initialization")
    source, output, executable, rom = map(lambda value: Path(value).resolve(),
                                          (source, output, executable, rom))
    if output.exists():
        raise FileExistsError(output)
    if digest(rom) != rom_sha256:
        raise ValueError("ROM identity mismatch")
    manifest = json.loads((source / "export-manifest.json").read_text())
    if manifest.get("kind") != "jfg-phase95-selected-input-export":
        raise ValueError("unsupported selected-input export")
    replay_source = source / "controller.input"
    if manifest.get("input_sha256") != digest(replay_source):
        raise ValueError("selected input changed after export")
    events = load_replay(replay_source)
    export_target = manifest.get("oracle_final_frame")
    if type(export_target) is not int or not 3 <= export_target <= 1000000 or \
            events[-1].last != export_target:
        raise ValueError("replay target is not the exported oracle frame")
    if stop_by_polls and target_retraces is not None:
        raise ValueError("poll-target replay cannot also stop by retraces")
    target = select_target(export_target, target_retraces)
    validate_execution_target(environment, target, stop_by_polls, poll_hashes=poll_hashes)
    focus = validate_focus(focus_updates, update_hashes)
    point_pcs, point_words = point_probe.validate(point_pcs, point_words, focus,
                                                 execution_profile == "original-os-probe")
    device_spec = device_event_probe.specification(device_events, point_pcs, focus,
        side="native", qualified_engine=execution_profile == "original-os-probe")
    environment.pop("JFG_PHASE9_DEVICE_EVENTS", None)
    if device_events:
        environment["JFG_PHASE9_DEVICE_EVENTS"] = "1"
    eret_spec = eret_transfer_probe.configure(environment, eret_transfers, device_spec)
    effect_spec = instruction_effect_probe.configure(environment, instruction_effect_update, device_spec, eret_spec)
    watch = validate_watch_word(watch_word, focus, True)
    word = validate_update_word(update_word, update_hashes)
    if type(controller_return) is not bool or (controller_return and not event_windows):
        raise ValueError("controller return requires bounded event windows")
    entry = validate_entry_target(entry_target, focus)
    fpu = validate_entry_fpu(entry_fpu, entry)
    memory = validate_entry_memory(entry_memory, entry)
    gpr = validate_entry_gpr(entry_gpr, entry)
    instruction_probe = validate_instruction_probe(instruction_probe, focus)
    if type(poll_hashes) is not bool:
        raise ValueError("poll_hashes must be a boolean")
    event_windows = validate_windows(event_windows, poll_hashes=poll_hashes,
                                     update_hashes=update_hashes)
    declared_polls = manifest.get("controller_polls")
    if type(declared_polls) is not int or not 1 <= declared_polls <= 1000000:
        raise ValueError("export lacks a bounded controller poll count")
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("replay timeout must be 1..3600 seconds")
    initial = manifest.get("initial_state")
    if not isinstance(initial, dict):
        raise ValueError("export lacks explicit candidate initial save/pak")
    for name, key in (("initial.flash", "flash_sha256"), ("initial.pak", "pak_sha256")):
        if digest(source / name) != initial.get(key):
            raise ValueError(f"exported {name} changed")
    output.mkdir(parents=True)
    shutil.copyfile(replay_source, output / "controller.input")
    shutil.copyfile(source / "initial.flash", output / "replay.flash")
    shutil.copyfile(source / "initial.pak", output / "replay.pak")
    objective = {"kind": "jfg-phase95-native-selected-poll-replay", "schema": 1,
                 "acceptance": False, "source_export": str(source),
                 "input_sha256": digest(output / "controller.input"),
                 "initial_flash_sha256": digest(output / "replay.flash"),
                 "initial_pak_sha256": digest(output / "replay.pak"),
                 "executable_sha256": digest(executable), "rom_sha256": rom_sha256,
                 "execution_profile": execution_profile or "legacy-environment",
                 "native_runtime_sha256": runtime_digest(executable.parent),
                 "oracle_final_frame": export_target,
                 "target_retraces": None if stop_by_polls else target,
                 "target_controller_polls": declared_polls if stop_by_polls else None,
                 "controller_polls": declared_polls,
                 "stop_mode": "controller-polls" if stop_by_polls else "vi-retraces",
                 "mode": "replay-by-poll", "poll_trace": poll_trace,
                 "poll_semantic_hashes": poll_hashes,
                 "event_windows": event_windows,
                 "completed_update_trace": bool(update_hashes),
                 "focused_update_range": focus,
                 "watch_word": f"0x{watch:08x}" if watch is not None else None,
                 "update_word": f"0x{word:08x}" if word is not None else None,
                 "controller_return": controller_return,
                 "controller_guest_init_probe":
                     environment.get("JFG_PHASE9_CONTROLLER_GUEST_INIT") == "1",
                 "si_count_probe": environment.get("JFG_PHASE9_SI_COUNT_PROBE") == "1",
                 "renderer_writeback_probe": environment.get("JFG_PHASE9_RENDERER_WRITEBACK_PROBE") == "1",
                 "guest_leaf_probe": environment.get("JFG_PHASE9_GUEST_LEAF_PROBE") == "1",
                 "guest_os_probe": environment.get("JFG_PHASE9_GUEST_OS_PROBE") == "1",
                 "guest_os_profile": "bounded-original-os-device-integration-not-accepted"
                     if environment.get("JFG_PHASE9_GUEST_OS_PROBE") == "1" else None,
                 "guest_leaf_boot_profile": "original-os-initialize-observed-cold-status-pif-not-device-timing"
                     if environment.get("JFG_PHASE9_GUEST_LEAF_PROBE") == "1" else None,
                 "guest_leaf_mi_profile": "observed-zero-boot-set-clear-mask-not-device-delivery"
                     if environment.get("JFG_PHASE9_GUEST_LEAF_PROBE") == "1" else None,
                 "guest_leaf_sp_profile": "reference-sync-dma-original-load-start-not-device-timing"
                     if environment.get("JFG_PHASE9_GUEST_LEAF_PROBE") == "1" else None,
                 "guest_leaf_cache_profile": "observed-coherent-reference-not-hardware"
                    if environment.get("JFG_PHASE9_GUEST_LEAF_PROBE") == "1" else None,
                 "guest_leaf_tlb_profile": "observed-mupen-zero-boot-first-match-not-hardware"
                     if environment.get("JFG_PHASE9_GUEST_LEAF_PROBE") == "1" else None,
                 "si_count_probe_profile": "observed-oracle-ack-2568-not-hardware"
                     if environment.get("JFG_PHASE9_SI_COUNT_PROBE") == "1" else None,
                 "entry_target": f"0x{entry:08x}" if entry is not None else None,
                 "entry_fpu": fpu,
                 "entry_memory": memory,
                 "entry_gpr": gpr,
                 "instruction_probe": instruction_probe,
                 "instruction_probe_pcs": [f"0x{pc:08x}" for pc in
                                           INSTRUCTION_PROBE_PCS] if instruction_probe else [],
                 "initial_save_equivalence": "not_verified",
                 "alignment_status": "not_verified",
                 "poll_stop_boundary":
                     "after-controller-read-hle-before-guest-response"
                     if stop_by_polls else None}
    if point_pcs:
        objective["point_probe"] = {"pcs": list(point_pcs), "words": list(point_words), "phase": point_probe.PHASE}
    if device_spec is not None:
        objective["device_events"] = device_spec
    if eret_spec is not None:
        objective["eret_transfers"] = eret_spec
    if effect_spec is not None:
        objective["instruction_effects"] = effect_spec
    (output / "native-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    if environment.get('JFG_PHASE9_GUEST_OS_PROBE') == '1':
        environment['JFG_PHASE9_GUEST_OS_CLOCK_TRACE'] = str(output / 'guest-os-clock.tsv')
    environment.update(JFG_PHASE8_INPUT_REPLAY=str(output / "controller.input"),
                       JFG_PHASE8_PROGRESS=str(output / "progress.json"),
                       JFG_PHASE9_REPLAY_BY_POLL="1", JFG_PHASE9_FAST_REPLAY="1",
                       JFG_PHASE9_RETRACE_HASH=str(output / "retrace-hashes.jsonl"))
    environment.pop("JFG_PHASE9_INPUT_RECORD", None)
    environment.pop("JFG_PHASE8_RDRAM_CAPTURE", None)
    if poll_trace:
        environment["JFG_PHASE95_NATIVE_POLL_TRACE"] = str(output / "controller-polls.tsv")
    else:
        environment.pop("JFG_PHASE95_NATIVE_POLL_TRACE", None)
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
    if controller_return:
        environment["JFG_PHASE9_CONTROLLER_RETURN"] = "1"
    else:
        environment.pop("JFG_PHASE9_CONTROLLER_RETURN", None)
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
        environment["JFG_PHASE9_ENTRY_TARGET"] = f"0x{entry:08x}"
    else:
        environment.pop("JFG_PHASE9_ENTRY_TARGET", None)
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
    if instruction_probe:
        environment["JFG_PHASE9_INSTRUCTION_PROBE"] = "1"
    else:
        environment.pop("JFG_PHASE9_INSTRUCTION_PROBE", None)
    for name, values in (("JFG_PHASE9_POINT_PCS", point_pcs), ("JFG_PHASE9_POINT_WORDS", point_words)):
        environment.pop(name, None)
        if values:
            environment[name] = point_probe.specification(values)
    started = time.monotonic()
    with (output / "stdout.log").open("wb") as stdout, \
            (output / "stderr.log").open("wb") as stderr, \
            WorkerJob(memory_limit_bytes=8 * 1024 * 1024 * 1024,
                      cpu_seconds=timeout) as guard:
        command = [str(executable), "--rom", str(rom), "--save",
                   str(output / "replay.flash"), "--controller-pak",
                   str(output / "replay.pak")]
        if stop_by_polls:
            command += ["--probe-polls", str(declared_polls),
                        "--watchdog-ms", str(timeout * 1000)]
        else:
            command += ["--probe-retraces", str(target)]
        process = subprocess.Popen(command, env=environment,
                                   stdout=stdout, stderr=stderr,
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
            raise TimeoutError("owned native replay exceeded declared wall-time budget") from error
        except BaseException:
            guard.close()
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=30)
            raise
    records = (output / "stdout.log").read_text().splitlines()
    probe_kind = "jfg-phase9-original-os-probe" if objective["guest_os_probe"] else "jfg-phase8-native-probe"
    probes = [json.loads(line) for line in records
              if line.startswith('{"kind":"' + probe_kind + '"')]
    probe = probes[0] if len(probes) == 1 else {}
    reached = (probe.get("status") == "poll-target" and
               type(probe.get("poll_target")) is int and
               probe["poll_target"] == declared_polls and
               type(probe.get("controller_samples")) is int and
               probe["controller_samples"] == declared_polls and
               type(probe.get("vi_retraces")) is int and
               probe["vi_retraces"] >= 0) if stop_by_polls else (
               probe.get("status") == "retrace-target" and
               type(probe.get("vi_retraces")) is int and
               probe["vi_retraces"] == target)
    update_path = output / "retrace-hashes.jsonl.updates.jsonl"
    update_count, update_error = trace_record_count(update_records, update_path) if \
        update_hashes else (0, None)
    word_path = output / "update-word.tsv"
    try:
        word_count = len(read_update_word(word_path, word)) if \
            word is not None else None
    except (OSError, ValueError):
        word_count = None
    word_complete = (word_count == update_count and word_count > 0) if \
        word is not None and word_count is not None else None
    poll_hash_path = output / "retrace-hashes.jsonl.polls.jsonl"
    poll_hash_count, poll_error = trace_record_count(poll_records, poll_hash_path, "native") if \
        poll_hashes else (0, None)
    try:
        event_count = len(read_event_trace(
            output / "retrace-hashes.jsonl.events.tsv", event_windows,
            "native")) if event_windows else None
    except (OSError, ValueError):
        event_count = None
    controller_return_path = output / "retrace-hashes.jsonl.controller-return.tsv"
    try:
        controller_return_count = len(read_controller_return(
            controller_return_path, tuple(event_windows))) if \
            controller_return else None
    except (OSError, ValueError):
        controller_return_count = None
    focus_complete = (all((output / f"focus-update-{index}.rdram").is_file() and
                          (output / f"focus-update-{index}.rdram").stat().st_size ==
                          4 * 1024 * 1024
                          for index in range(focus[0], focus[1] + 1))
                      if focus is not None else None)
    watch_lines = (output / "watch-word.tsv").read_text(encoding="utf-8").splitlines() \
        if watch is not None and (output / "watch-word.tsv").is_file() else []
    watch_complete = (bool(watch_lines) and
                      watch_lines[0].startswith("update_candidate\tvi_retraces\t") and
                      len(watch_lines) <= 1025) if watch is not None else None
    entry_lines = (output / "entry-args.tsv").read_text(encoding="utf-8").splitlines() \
        if entry is not None and (output / "entry-args.tsv").is_file() else []
    entry_complete = (len(entry_lines) >= 2 and
                      entry_lines[0].startswith("update_candidate\tvi_retraces\t") and
                      len(entry_lines) <= 1025) if entry is not None else None
    fpu_lines = (output / "entry-fpu.tsv").read_text(encoding="utf-8").splitlines() \
        if fpu and (output / "entry-fpu.tsv").is_file() else []
    fpu_header = ("update_candidate", "vi_retraces", "controller_polls",
                  "target", *(field for index in range(32)
                  for field in (f"f{index}_lo", f"f{index}_hi")))
    fpu_complete = (entry_complete and len(fpu_lines) == len(entry_lines) and
                    tuple(fpu_lines[0].split("\t")) == fpu_header and
                    all(len(line.split("\t")) == len(fpu_header) for line in
                        fpu_lines[1:])) if fpu else None
    memory_lines = (output / "entry-memory.tsv").read_text(
        encoding="utf-8").splitlines() if memory and (
            output / "entry-memory.tsv").is_file() else []
    memory_header = ("update_candidate", "vi_retraces", "controller_polls",
                     "target", "a1_256", "a2_256", "a3_256")
    memory_complete = (entry_complete and
                       len(memory_lines) == len(entry_lines) and
                       tuple(memory_lines[0].split("\t")) == memory_header and
                       all(len(line.split("\t")) == len(memory_header) and
                           all(len(word) == 512 for word in line.split("\t")[4:])
                           for line in memory_lines[1:])) if memory else None
    gpr_lines = (output / "entry-gpr.tsv").read_text(
        encoding="utf-8").splitlines() if gpr and (
            output / "entry-gpr.tsv").is_file() else []
    gpr_header = ("update_candidate", "vi_retraces", "controller_polls",
                  "target", *(field for index in range(32)
                  for field in (f"r{index}_lo", f"r{index}_hi")))
    gpr_complete = (entry_complete and len(gpr_lines) == len(entry_lines) and
                    tuple(gpr_lines[0].split("\t")) == gpr_header and
                    all(len(line.split("\t")) == len(gpr_header) for line in
                        gpr_lines[1:])) if gpr else None
    instruction_lines = (output / "instruction-probe.tsv").read_text(
        encoding="utf-8").splitlines() if instruction_probe and (
            output / "instruction-probe.tsv").is_file() else []
    instruction_rows = [line.split("\t") for line in instruction_lines[1:]]
    instruction_pcs = {f"0x{pc:08x}" for pc in INSTRUCTION_PROBE_PCS}
    instruction_complete = (
        len(INSTRUCTION_PROBE_PCS) + 1 <= len(instruction_lines) <= 1025 and
        tuple(instruction_lines[0].split("\t")) == INSTRUCTION_PROBE_HEADER and
        all(len(row) == len(INSTRUCTION_PROBE_HEADER) and
            row[3] in instruction_pcs for row in instruction_rows) and
        {row[3] for row in instruction_rows} == instruction_pcs
    ) if instruction_probe else None
    result = {**objective, "exit_code": exit_code,
              "elapsed_seconds": time.monotonic() - started,
              "probe_target_reached": len(probes) == 1 and reached,
              "completed_update_count": update_count if update_hashes else None,
              "completed_update_trace_complete": update_count > 0 if update_hashes else None,
              "update_word_trace_complete": word_complete,
              "update_word_trace_sha256": digest(word_path)
              if word_complete else None,
              "poll_semantic_hash_count": poll_hash_count if poll_hashes else None,
              "event_trace_rows": event_count,
              "event_trace_complete": event_count is not None
              if event_windows else None,
              "controller_return_rows": controller_return_count,
              "controller_return_trace_complete":
                  controller_return_count is not None
                  if controller_return else None,
              "controller_return_trace_sha256": digest(controller_return_path)
                  if controller_return_count is not None else None,
              "poll_semantic_hash_sha256": digest(poll_hash_path)
              if poll_hashes and poll_hash_path.is_file() else None,
              "poll_semantic_hash_trace_complete": (
                  poll_hash_count > 0 and poll_hash_count == probe.get("controller_samples")
              ) if poll_hashes else None,
              "focused_update_capture_complete": focus_complete,
              "watch_word_trace_complete": watch_complete,
              "watch_dispatch_changes": len(watch_lines) - 1 if watch_complete else None,
              "entry_trace_complete": entry_complete,
              "entry_fpu_trace_complete": fpu_complete,
              "entry_memory_trace_complete": memory_complete,
              "entry_gpr_trace_complete": gpr_complete,
              "instruction_probe_trace_complete": instruction_complete,
              "instruction_probe_hits": len(instruction_rows) if instruction_probe else None,
              "entry_hits": len(entry_lines) - 1 if entry_complete else None,
              "actual_vi_retraces": probe.get("vi_retraces") if probe else None,
              "final_state_hash": probe.get("state_hash") if probe else None,
              "trace_parse_errors": {key: error for key, error in
                  (("completed_updates", update_error), ("controller_polls", poll_error))
                  if error is not None}}
    if len(probes) == 1:
        result.update(poll_completion(declared_polls,
                                      probe.get("controller_samples")))
    if point_pcs:
        result["point_probe"] = {**objective["point_probe"], **point_probe.summary(
            output / "point-probe.tsv", point_pcs, point_words, focus, oracle=False)}
        if result["point_probe"]["complete"]:
            result["point_probe"]["sha256"] = digest(output / "point-probe.tsv")
    if device_spec is not None:
        result["device_events"] = {**device_spec, **device_event_probe.summary(
            output / "device-events.tsv", device_spec, side="native")}
        if result["device_events"]["complete"]:
            result["device_events"]["sha256"] = digest(output / "device-events.tsv")
    if eret_spec is not None:
        result["eret_transfers"] = {**eret_spec, **eret_transfer_probe.summary(
            output / "eret-transfers.tsv", eret_spec)}
        if result["eret_transfers"]["complete"]:
            result["eret_transfers"]["sha256"] = digest(output / "eret-transfers.tsv")
    if effect_spec is not None:
        result["instruction_effects"] = {**effect_spec, **instruction_effect_probe.summary(
            output / "instruction-effects.bin", instruction_effect_update)}
        if result["instruction_effects"]["complete"]:
            result["instruction_effects"]["sha256"] = digest(output / "instruction-effects.bin")
    (output / "native-result.json").write_text(json.dumps(result, indent=2) + "\n")
    if exit_code != 0 or not result["probe_target_reached"] or \
            (update_hashes and update_count == 0) or \
            (word is not None and not word_complete) or \
            (poll_hashes and not result["poll_semantic_hash_trace_complete"]) or \
            (event_windows and not result["event_trace_complete"]) or \
            (controller_return and controller_return_count is None) or \
            (focus is not None and (update_count < focus[1] or not focus_complete)) or \
            (watch is not None and not watch_complete) or \
            (entry is not None and not entry_complete) or \
            (fpu and not fpu_complete) or \
            (memory and not memory_complete) or \
            (gpr and not gpr_complete) or \
            (instruction_probe and not instruction_complete) or \
            (point_pcs and not result["point_probe"]["complete"]) or \
            (device_events and not result["device_events"]["complete"]) or \
            (eret_transfers and not result["eret_transfers"]["complete"]) or \
            (effect_spec is not None and not result["instruction_effects"]["complete"]):
        raise RuntimeError(f"native replay failed its bounded target: {output}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-events", action="store_true", help="observe bounded instruction/device phases with an instrumented runtime")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--execution-profile", choices=EXECUTION_PROFILES,
                        help="explicit, shell-independent runtime profile; omitted preserves legacy probe flags")
    parser.add_argument("--poll-trace", action="store_true")
    parser.add_argument("--poll-hashes", action="store_true",
                        help="capture pre-input semantic state at each controller poll")
    parser.add_argument("--event-window", action="append", default=[],
                        metavar="FIRST:LAST",
                        help="capture a bounded controller/update/VI event window")
    parser.add_argument("--stop-by-polls", action="store_true",
                        help="stop at exactly the declared controller poll count")
    parser.add_argument("--target-retraces", type=int,
                        help="bounded diagnostic prefix of exported route")
    parser.add_argument("--update-hashes", action="store_true",
                        help="capture hashes after completed guest updates")
    parser.add_argument("--focus-updates", nargs=2, type=int, metavar=("FIRST", "LAST"),
                        help="capture canonical RDRAM at 1..16 completed updates")
    parser.add_argument("--watch-word", type=lambda value: int(value, 0),
                        help="trace dispatches changing a focused KSEG0 word")
    parser.add_argument("--update-word", type=lambda value: int(value, 0),
                        help="capture one KSEG0 word after every completed update")
    parser.add_argument("--controller-return", action="store_true",
                        help="capture guest pad bytes after bounded GetReadData calls")
    parser.add_argument("--entry-target", type=lambda value: int(value, 0),
                        help="trace A0-A3 at a focused generated function entry")
    parser.add_argument("--entry-fpu", action="store_true",
                        help="capture raw FPU register words at focused entry")
    parser.add_argument("--entry-memory", action="store_true",
                        help="capture 256 input bytes from each A1-A3 pointer at entry")
    parser.add_argument("--entry-gpr", action="store_true",
                        help="capture raw GPR register words at focused entry")
    parser.add_argument("--instruction-probe", action="store_true",
                        help="capture focused guest decode PCs from a diagnostic build")
    parser.add_argument("--point-pc", action="append", default=[], type=lambda value: int(value, 0),
                        help="observe registers before a focused original-OS guest instruction (max 16)")
    parser.add_argument("--point-word", action="append", default=[], type=lambda value: int(value, 0),
                        help="read a KSEG0 word at each point (max 16)")
    parser.add_argument("--eret-transfers", action="store_true",
                        help="capture native ERET boundaries before host handoff; requires --device-events")
    parser.add_argument("--instruction-effect-update", type=int,
                        help="capture paired instruction effects at one invocation; requires device and ERET capture")
    args = parser.parse_args()
    try:
        event_windows = [tuple(map(int, value.split(":")))
                         for value in args.event_window]
    except ValueError as error:
        parser.error(f"invalid --event-window: {error}")
    print(json.dumps(replay(args.source, args.output, args.executable,
                            args.rom, args.rom_sha256, timeout=args.timeout,
                            execution_profile=args.execution_profile,
                            poll_trace=args.poll_trace,
                            stop_by_polls=args.stop_by_polls,
                            target_retraces=args.target_retraces,
                            update_hashes=args.update_hashes,
                            poll_hashes=args.poll_hashes,
                            event_windows=event_windows,
                            focus_updates=args.focus_updates,
                            watch_word=args.watch_word,
                            update_word=args.update_word,
                            controller_return=args.controller_return,
                            entry_target=args.entry_target,
                            entry_fpu=args.entry_fpu,
                            entry_memory=args.entry_memory,
                            entry_gpr=args.entry_gpr,
                            instruction_probe=args.instruction_probe,
                            point_pcs=args.point_pc, point_words=args.point_word, device_events=args.device_events,
                            eret_transfers=args.eret_transfers,
                            instruction_effect_update=args.instruction_effect_update)))


if __name__ == "__main__":
    main()
