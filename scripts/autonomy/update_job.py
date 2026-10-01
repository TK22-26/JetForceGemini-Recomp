"""Pinned, restartable completed-guest-update comparison job.

This is a diagnostic prefix, not an input/initial-state or whole-route parity gate.
"""

from __future__ import annotations

import hashlib
import argparse
import json
from pathlib import Path
import subprocess
import time
from typing import Any

from scripts.autonomy.job_store import JobSpec, JobStore, JobStoreError, ID_RE, SHA256_RE
from scripts.autonomy import execution_contract as execution
from scripts.autonomy import source_build
from scripts.autonomy.process_guard import real_python_executable
from scripts.autonomy.supervisor import (
    PIN_FILES, SupervisorError, _git_ok, _inside, _write_json_atomic,
    bounded_command, canonical_bytes, expired_attempt_contained, file_sha256,
)
from scripts.compare_phase9_update_hashes import compare
from scripts.compare_phase9_focus_rdram import compare as compare_focus
from scripts.phase9_update_poll_alignment import diagnose as diagnose_poll_alignment
from scripts.phase95_poll_compare import (
    compare as compare_polls, oracle_polls, native_polls,
)


TOOL_FILES = (
    "scripts/autonomy/atomic_file.py",
    "scripts/autonomy/update_job.py",
    "scripts/autonomy/execution_contract.py",
    "scripts/autonomy/entry_plan.py",
    "scripts/autonomy/experiment_plan.py",
    "scripts/autonomy/entry_plan.schema.json",
    "scripts/autonomy/point_plan.py",
    "scripts/autonomy/point_plan.schema.json",
    "scripts/autonomy/experiment.schema.json",
    "scripts/autonomy/source_build.py",
    "scripts/autonomy/source_snapshot.py",
    "scripts/phase95_bridge.py",
    "scripts/phase95_native_replay.py",
    "scripts/phase9_point_probe.py",
    "scripts/phase95_oracle_replay.py",
    "scripts/phase9_oracle_instruction_effects.py",
    "scripts/phase9_bizhawk_oracle.lua",
    "scripts/phase9_si_trace.py",
    "scripts/compare_phase9_update_hashes.py",
    "scripts/compare_phase9_retrace_hashes.py",
    "scripts/phase9_update_poll_alignment.py",
    "scripts/phase95_poll_compare.py",
    "scripts/compare_phase9_focus_rdram.py",
)


def tool_sha256(repo: Path) -> str:
    digest = hashlib.sha256()
    for relative in TOOL_FILES:
        digest.update(relative.encode("ascii"))
        digest.update(bytes.fromhex(file_sha256(repo / relative)))
    return digest.hexdigest()


def pins(packet: dict[str, Any], repo: Path) -> dict[str, str]:
    return {"source_commit": packet["source_commit"],
            "tool_sha256": tool_sha256(repo),
            **{key + "_sha256": file_sha256(Path(packet["pin_files"][key]))
               for key in PIN_FILES}}


def validate(packet: dict[str, Any], repo: Path) -> None:
    required = {"schema", "job_id", "source_commit", "pin_files",
                "source_export", "alignment_id", "evidence_files",
                "native_target", "oracle_target", "timeout_seconds"}
    optional = {"predecessor_id", "focus_updates", "focus_pair", "execution", "source_build", "entry_probe", "point_probe"}
    if (not isinstance(packet, dict) or
            not required <= set(packet) or not set(packet) <= required | optional or
            packet["schema"] != 1):
        raise SupervisorError("invalid update packet schema")
    execution.validate(packet)
    if "point_probe" in packet:
        from scripts.autonomy.point_plan import validate_probe
        validate_probe(packet["point_probe"])
        if ("entry_probe" in packet or "focus_updates" not in packet or "source_build" not in packet or
                packet.get("execution", {}).get("profile") != "original-os-probe"):
            raise SupervisorError("point capture needs a focused frozen-source original-OS build and no other entry probe")
    if "entry_probe" in packet:
        from scripts.autonomy.entry_plan import validate_probe
        validate_probe(packet["entry_probe"])
        if ("focus_updates" not in packet or "source_build" not in packet or
                packet.get("execution", {}).get("profile") != "original-os-probe"):
            raise SupervisorError("entry capture needs a focused frozen-source original-OS baseline")
    if (packet.get("execution", {}).get("profile") == "original-os-probe" and
            (type(packet["native_target"]) is not int or packet["native_target"] < 4)):
        raise SupervisorError("original OS update capture requires at least 4 VI")
    if ("focus_updates" in packet) != ("focus_pair" in packet):
        raise SupervisorError("focused update range and pair must travel together")
    if "focus_updates" in packet:
        window, pair = packet["focus_updates"], packet["focus_pair"]
        if (not isinstance(window, list) or len(window) != 2 or
                any(type(value) is not int or value < 1 for value in window) or
                not 0 <= window[1] - window[0] < 16 or
                not isinstance(pair, dict) or
                set(pair) != {"native_before", "oracle_before", "native_after",
                              "oracle_after"} or
                any(type(value) is not int or not window[0] <= value <= window[1]
                    for value in pair.values()) or
                pair["native_after"] != pair["native_before"] + 1 or
                pair["oracle_after"] != pair["oracle_before"] + 1):
            raise SupervisorError("invalid focused update window or pair")
    if any(not isinstance(packet[key], str) or not ID_RE.fullmatch(packet[key])
           for key in ("job_id", "alignment_id")):
        raise SupervisorError("invalid update job ID")
    if ("predecessor_id" in packet and
            (not isinstance(packet["predecessor_id"], str) or
             not ID_RE.fullmatch(packet["predecessor_id"]))):
        raise SupervisorError("invalid update predecessor ID")
    if (not isinstance(packet["source_commit"], str) or
            len(packet["source_commit"]) not in (40, 64) or
            _git_ok(repo, "rev-parse", "--verify",
                    packet["source_commit"] + "^{commit}") != packet["source_commit"]):
        raise SupervisorError("update source commit is invalid")
    if (not isinstance(packet["pin_files"], dict) or
            set(packet["pin_files"]) != set(PIN_FILES)):
        raise SupervisorError("update binary pins are incomplete")
    for key in PIN_FILES:
        value = packet["pin_files"][key]
        if not isinstance(value, str) or not Path(value).is_absolute() or not Path(value).is_file():
            raise SupervisorError("update binary pin is missing")
    if "source_build" in packet:
        build = source_build.validate(repo, packet["source_build"],
                                      Path(packet["pin_files"]["native"]))
        if packet["source_commit"] != build["source_commit"]:
            raise SupervisorError("update source differs from its recorded build")
    source = packet["source_export"]
    if (not isinstance(source, str) or not Path(source).is_absolute() or
            not Path(source).is_dir() or
            not _inside(Path(source), repo / "tools" / "private")):
        raise SupervisorError("update source must be private")
    manifest = json.loads((Path(source) / "export-manifest.json").read_text(encoding="utf-8"))
    final = manifest.get("oracle_final_frame")
    if (manifest.get("kind") != "jfg-phase95-selected-input-export" or
            type(final) is not int or not 3 <= final <= 1_000_000 or
            type(packet["native_target"]) is not int or
            type(packet["oracle_target"]) is not int or
            not 3 <= packet["native_target"] <= packet["oracle_target"] <= final or
            type(packet["timeout_seconds"]) is not int or
            not 60 <= packet["timeout_seconds"] <= 1800):
        raise SupervisorError("update capture limits are invalid")
    files = packet["evidence_files"]
    if not isinstance(files, list) or not 5 <= len(files) <= 12:
        raise SupervisorError("update evidence list is invalid")
    for item in files:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"} or
                not isinstance(item["path"], str) or
                not isinstance(item["sha256"], str) or
                not SHA256_RE.fullmatch(item["sha256"])):
            raise SupervisorError("invalid update evidence pin")
        path = Path(item["path"])
        if (not path.is_absolute() or not path.is_file() or
                not _inside(path, repo / "tools" / "private") or
                file_sha256(path) != item["sha256"]):
            raise SupervisorError("update evidence changed or escaped private storage")


def queue_update(store: JobStore, repo: Path, state: Path, *, job_id: str,
                 alignment_id: str, alignment_result: Path,
                 alignment_packet: dict[str, Any], native_target: int | None = None,
                 predecessor_id: str | None = None,
                 focus_pair: dict[str, int] | None = None,
                 execution_profile: str | None = None,
                 build_binding: dict[str, str] | None = None,
                 entry_probe: dict[str, str] | None = None,
                 point_probe: dict | None = None) -> None:
    source = Path(alignment_packet["source_export"]).resolve(strict=True)
    export = json.loads((source / "export-manifest.json").read_text(encoding="utf-8"))
    final = export["oracle_final_frame"]
    native_target = min(600, final) if native_target is None else native_target
    if type(native_target) is not int or not 3 <= native_target <= final:
        raise SupervisorError("update target exceeds exported route")
    oracle_target = min(final, native_target * 3 // 2)
    files = [source / name for name in ("export-manifest.json", "controller.input",
                                       "initial.flash", "initial.pak")]
    files.append(alignment_result.resolve(strict=True))
    packet = {
        "schema": 1, "job_id": job_id,
        "source_commit": _git_ok(repo, "rev-parse", "HEAD"),
        "pin_files": alignment_packet["pin_files"],
        "source_export": str(source), "alignment_id": alignment_id,
        "evidence_files": [{"path": str(path), "sha256": file_sha256(path)}
                           for path in files],
        "native_target": native_target, "oracle_target": oracle_target,
        "timeout_seconds": 900,
    }
    binding = build_binding if build_binding is not None else alignment_packet.get("source_build")
    if binding is not None:
        build = source_build.validate(repo, binding, Path(packet["pin_files"]["native"]))
        packet["source_commit"] = build["source_commit"]
        packet["source_build"] = binding
    if predecessor_id is not None:
        packet["predecessor_id"] = predecessor_id
    inherited_profile = alignment_packet.get("execution", {}).get("profile")
    if execution_profile is not None and inherited_profile is not None and \
            execution_profile != inherited_profile:
        raise SupervisorError("update successor cannot change execution profile")
    profile = execution_profile if execution_profile is not None else inherited_profile
    if profile is not None:
        packet["execution"] = execution.capture(packet["pin_files"], profile)
    if focus_pair is not None:
        packet["focus_pair"] = focus_pair
        packet["focus_updates"] = [min(focus_pair.values()), max(focus_pair.values())]
        if profile == "original-os-probe":
            # Include the preceding pacing update, not only the later actor
            # mismatch. This is capture coverage, never an index shift.
            packet["focus_updates"] = [max(1, packet["focus_updates"][0] - 1),
                                       packet["focus_updates"][1] + 1]
    if entry_probe is not None:
        packet["entry_probe"] = entry_probe
        packet["timeout_seconds"] = 660
    if point_probe is not None:
        packet["point_probe"] = point_probe
        packet["timeout_seconds"] = 660
    validate(packet, repo)
    state.mkdir(parents=True, exist_ok=True)
    encoded = canonical_bytes(packet)
    digest = hashlib.sha256(encoded).hexdigest()
    packet_dir = state / "update-packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    target = packet_dir / (job_id + ".json")
    if target.exists() and target.read_bytes() != encoded:
        raise SupervisorError("update job ID already names a different packet")
    if not target.exists():
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(target)
    store.enqueue(JobSpec(job_id, pins(packet, repo),
                          ("update-packet:" + digest,),
                          (predecessor_id or alignment_id,),
                          "emulator:bizhawk", 1, "json_complete"))


def point_cli(packet):
    probe = packet.get("point_probe")
    return [arg for field,flag in (("pcs","--point-pc"),("words","--point-word"))
            for value in (probe[field] if probe else []) for arg in (flag,value)]


def point_trace_pins(packet, directory, native, oracle):
    if "point_probe" not in packet:
        return {}
    from scripts import phase9_point_probe as point
    probe = packet["point_probe"]
    pcs, words = [int(x,16) for x in probe["pcs"]], [int(x,16) for x in probe["words"]]
    result = {}
    for side,manifest in (("native",native),("oracle",oracle)):
        report = manifest.get("point_probe", {})
        relative = f"{side}/point-probe.tsv"
        digest = file_sha256(directory / relative)
        if (report.get("complete") is not True or report.get("pcs") != pcs or report.get("words") != words or
                report.get("phase") != point.PHASE or report.get("sha256") != digest):
            raise SupervisorError("point capture declaration/completion/hash differs")
        rows = point.read(directory / relative, pcs, words, packet["focus_updates"], oracle=side == "oracle")
        if report.get("events") != len(rows):
            raise SupervisorError("point capture event count differs")
        result[relative] = digest
    return result


def _recover(store: JobStore, lease: dict[str, Any], prior: Path,
             packet: dict[str, Any]) -> bool:
    result_path = prior / "result.json"
    if not result_path.is_file():
        return False
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("complete") is not True:
        return False
    expected = lease["spec"]["inputs"][0].split(":", 1)[1]
    report_path = prior / "update-comparison.json"
    native_path = prior / "native" / "native-result.json"
    oracle_path = prior / "oracle" / "oracle-result.json"
    native_trace = prior / "native" / "retrace-hashes.jsonl.updates.jsonl"
    oracle_trace = prior / "oracle" / "update-hashes.jsonl"
    oracle_vi_trace = prior / "oracle" / "consumed-vi-hashes.jsonl"
    alignment_path = prior / "update-alignment.json"
    poll_path = prior / "input-poll-comparison.json"
    focus_path = prior / "focus-comparison.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    if (result.get("kind") != "update-execution" or
            result.get("job_id") != lease["job_id"] or
            result.get("packet_sha256") != expected or
            result.get("pins") != lease["spec"]["pins"] or
            any(not path.is_file() for path in (
                report_path, native_path, oracle_path, native_trace, oracle_trace)) or
            result.get("comparison_sha256") != file_sha256(report_path) or
            result.get("native_result_sha256") != file_sha256(native_path) or
            result.get("oracle_result_sha256") != file_sha256(oracle_path) or
            result.get("native_trace_sha256") != file_sha256(native_trace) or
            result.get("oracle_trace_sha256") != file_sha256(oracle_trace) or
            (result.get("oracle_vi_trace_sha256") is not None and
             (not oracle_vi_trace.is_file() or
              result["oracle_vi_trace_sha256"] != file_sha256(oracle_vi_trace))) or
            (result.get("alignment_diagnostic_sha256") is not None and
             (not alignment_path.is_file() or
              result["alignment_diagnostic_sha256"] != file_sha256(alignment_path))) or
            (result.get("input_poll_comparison_sha256") is not None and
             (not poll_path.is_file() or
              result["input_poll_comparison_sha256"] != file_sha256(poll_path))) or
            (result.get("focus_comparison_sha256") is not None and
             (not focus_path.is_file() or
              result["focus_comparison_sha256"] != file_sha256(focus_path))) or
            any(file_sha256(prior / name) != digest
                for name, digest in result.get("focus_snapshot_sha256", {}).items()) or
            ("entry_probe" in packet and
             (set(result.get("entry_trace_sha256", {})) != {
                 f"{side}/entry-{kind}.tsv" for side in ("native", "oracle") for kind in ("args", "gpr")} or
              any(file_sha256(prior / name) != digest
                  for name, digest in result["entry_trace_sha256"].items()))) or
            ("point_probe" in packet and
             (set(result.get("point_trace_sha256", {})) != {"native/point-probe.tsv", "oracle/point-probe.tsv"} or
              any(file_sha256(prior / name) != digest for name,digest in result["point_trace_sha256"].items()))) or
            report.get("kind") != "jfg-phase9-update-comparison" or
            report.get("scope") != "prefix" or
            result.get("compared_updates") != report.get("compared_updates") or
            result.get("prefix_match") is not report.get("match") or
            result.get("first_divergence") != report.get("first_divergence") or
            result.get("parity_verified") is not False):
        raise SupervisorError("expired update bundle is inconsistent")
    execution.check_native(packet, json.loads(native_path.read_text(encoding="utf-8")))
    execution.check_oracle(packet, json.loads(oracle_path.read_text(encoding="utf-8")))
    point_trace_pins(packet, prior, json.loads(native_path.read_text()), json.loads(oracle_path.read_text()))
    store.start(lease["job_id"], lease["token"])
    store.verify(lease["job_id"], lease["token"])
    store.seal_artifact(lease["job_id"], lease["token"], result_path)
    store.pass_job(lease["job_id"], lease["token"])
    return True


def run_update_lease(store: JobStore, lease: dict[str, Any],
                     repo: Path, state: Path) -> str:
    job_id, token, attempt = lease["job_id"], lease["token"], lease["attempt"]
    attempt_dir = state / "attempts" / job_id / f"{attempt:04d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    result_path = attempt_dir / "result.json"
    try:
        packet = json.loads((state / "update-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        validate(packet, repo)
        execution.require_current(packet)
        digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (lease["spec"]["inputs"] != ["update-packet:" + digest] or
                pins(packet, repo) != lease["spec"]["pins"] or
                lease["spec"]["prerequisites"] != [
                    packet.get("predecessor_id", packet["alignment_id"])]):
            raise SupervisorError("update packet or tool pins changed")
        for previous in store.attempt_history(job_id):
            if previous["number"] >= attempt or previous["outcome"] != "expired":
                continue
            prior = state / "attempts" / job_id / f"{previous['number']:04d}"
            if list(prior.glob("*.guard.json")) or (prior / "result.json").is_file():
                if not expired_attempt_contained(prior):
                    raise SupervisorError("expired update child may still be alive")
                if _recover(store, lease, prior, packet):
                    return f"{job_id}: prior update comparison recovered"
        store.start(job_id, token)
        deadline = time.monotonic() + packet["timeout_seconds"]
        heartbeat = lambda: store.heartbeat(job_id, token, ttl=120)
        base = [real_python_executable(), "-m"]
        side_timeout = 300 if "entry_probe" in packet or "point_probe" in packet else packet["timeout_seconds"] - 30
        native_output = attempt_dir / "native"
        command = base + ["scripts.phase95_native_replay", packet["source_export"],
                          str(native_output), "--executable", packet["pin_files"]["native"],
                          "--rom", packet["pin_files"]["rom"], "--rom-sha256",
                          lease["spec"]["pins"]["rom_sha256"], "--target-retraces",
                          str(packet["native_target"]), "--update-hashes", "--poll-trace",
                          "--timeout",
                          str(side_timeout)]
        command += execution.cli(packet)
        if "focus_updates" in packet:
            command += ["--focus-updates", *map(str, packet["focus_updates"])]
        if "entry_probe" in packet:
            command += ["--entry-target", packet["entry_probe"]["entry_pc"], "--entry-gpr"]
        command += point_cli(packet)
        code, reason = bounded_command(
            command, repo, attempt_dir / "native.stdout", attempt_dir / "native.stderr",
            deadline, heartbeat, state / "PAUSED",
            guard_record=attempt_dir / "native.guard.json")
        if code != 0 or reason:
            raise SupervisorError("bounded native update capture failed")
        oracle_output = attempt_dir / "oracle"
        command = base + ["scripts.phase95_oracle_replay", str(oracle_output),
                          "--emulator", packet["pin_files"]["emulator"],
                          "--rom", packet["pin_files"]["rom"], "--rom-sha256",
                          lease["spec"]["pins"]["rom_sha256"], "--source",
                          packet["source_export"], "--target-frame",
                          str(packet["oracle_target"]), "--update-hashes", "--timeout",
                          str(side_timeout)]
        if "focus_updates" in packet:
            command += ["--vi-trace", "--focus-updates",
                        *map(str, packet["focus_updates"])]
        if "entry_probe" in packet:
            command += ["--entry-pc", packet["entry_probe"]["entry_pc"], "--entry-gpr"]
        command += point_cli(packet)
        code, reason = bounded_command(
            command, repo, attempt_dir / "oracle.stdout", attempt_dir / "oracle.stderr",
            deadline, heartbeat, state / "PAUSED",
            guard_record=attempt_dir / "oracle.guard.json")
        if code != 0 or reason:
            raise SupervisorError("bounded oracle update capture failed")
        native_path = native_output / "native-result.json"
        oracle_path = oracle_output / "oracle-result.json"
        native_trace = native_output / "retrace-hashes.jsonl.updates.jsonl"
        oracle_trace = oracle_output / "update-hashes.jsonl"
        oracle_vi_trace = oracle_output / "consumed-vi-hashes.jsonl"
        native = json.loads(native_path.read_text(encoding="utf-8"))
        oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
        execution.check_native(packet, native)
        execution.check_oracle(packet, oracle)
        entry_traces = {}
        point_traces = point_trace_pins(packet, attempt_dir, native, oracle)
        if "entry_probe" in packet:
            for side, manifest, target_key in (("native", native, "entry_target"), ("oracle", oracle, "entry_pc")):
                if (manifest.get("entry_trace_complete") is not True or
                        manifest.get("entry_gpr_trace_complete") is not True or
                        manifest.get(target_key) != packet["entry_probe"]["entry_pc"]):
                    raise SupervisorError("entry register capture is incomplete or changed target")
                for kind in ("args", "gpr"):
                    relative = f"{side}/entry-{kind}.tsv"
                    entry_traces[relative] = file_sha256(attempt_dir / relative)
        export = json.loads((Path(packet["source_export"]) /
                             "export-manifest.json").read_text(encoding="utf-8"))
        initial = export.get("initial_state") or {}
        count = native.get("completed_update_count")
        if (native.get("probe_target_reached") is not True or
                native.get("exit_code") != 0 or oracle.get("exit_code") != 0 or
                oracle.get("trace_complete") is not True or
                oracle.get("initial_flash_matches_candidate") is not True or
                native.get("completed_update_trace") is not True or
                oracle.get("completed_update_trace") is not True or
                native.get("completed_update_trace_complete") is not True or
                oracle.get("completed_update_trace_complete") is not True or
                ("focus_pair" in packet and
                 (oracle.get("vi_consumed_trace_complete") is not True or
                  not oracle_vi_trace.is_file())) or
                native.get("source_export") != packet["source_export"] or
                oracle.get("source_export") != packet["source_export"] or
                native.get("input_sha256") != export.get("input_sha256") or
                oracle.get("input_sha256") != export.get("input_sha256") or
                oracle.get("source_export_sha256") !=
                    file_sha256(Path(packet["source_export"]) / "export-manifest.json") or
                native.get("initial_flash_sha256") != initial.get("flash_sha256") or
                native.get("initial_pak_sha256") != initial.get("pak_sha256") or
                oracle.get("oracle_initial_flash_sha256") != initial.get("flash_sha256") or
                native.get("rom_sha256") != lease["spec"]["pins"]["rom_sha256"] or
                oracle.get("rom_sha256") != lease["spec"]["pins"]["rom_sha256"] or
                native.get("executable_sha256") != lease["spec"]["pins"]["native_sha256"] or
                oracle.get("emulator_sha256") != lease["spec"]["pins"]["emulator_sha256"] or
                native.get("target_retraces") != packet["native_target"] or
                oracle.get("target_frame") != packet["oracle_target"] or
                type(count) is not int or count < 1 or
                type(oracle.get("completed_update_count")) is not int or
                oracle["completed_update_count"] < count):
            raise SupervisorError("update captures lack a shared completed prefix")
        report = compare(native_trace, oracle_trace, count)
        report_path = attempt_dir / "update-comparison.json"
        _write_json_atomic(report_path, report)
        poll_prefix = min(len(oracle_polls(oracle_output / "checkpoints.tsv")),
                          len(native_polls(native_output / "controller-polls.tsv")),
                          export["controller_polls"])
        poll_path = attempt_dir / "input-poll-comparison.json"
        poll_report = compare_polls(packet["source_export"], oracle_output,
                                    native_output, poll_path,
                                    prefix_polls=poll_prefix)
        alignment_path = attempt_dir / "update-alignment.json"
        alignment_classification = None
        if not report["match"]:
            first = report["first_divergence"] or {}
            if type(first.get("update")) is int:
                try:
                    alignment = diagnose_poll_alignment(native_trace, oracle_trace,
                                                        first["update"])
                except ValueError as error:
                    if "lacks controller-poll metadata" not in str(error):
                        raise
                    alignment = {
                        "kind": "jfg-phase9-update-poll-alignment", "schema": 1,
                        "first_raw_mismatch_update": first["update"],
                        "classification": "clock-metadata-unavailable",
                        "same_poll_anchor": None, "matched_update_run": 0,
                        "alignment_validated": False, "parity_verified": False,
                    }
                _write_json_atomic(alignment_path, alignment)
                alignment_classification = alignment["classification"]
        focus_path = attempt_dir / "focus-comparison.json"
        focus_snapshots: dict[str, str] = {}
        if "focus_pair" in packet:
            focused = compare_focus(native_output, oracle_output,
                                    **packet["focus_pair"])
            if focused["vi_consumption_between"]["oracle_counter_available"] is not True:
                raise SupervisorError("focused oracle VI counter is unavailable")
            _write_json_atomic(focus_path, focused)
            for side in ("native", "oracle"):
                for update in range(packet["focus_updates"][0],
                                    packet["focus_updates"][1] + 1):
                    relative = f"{side}/focus-update-{update}.rdram"
                    focus_snapshots[relative] = file_sha256(attempt_dir / relative)
        validate(packet, repo)
        execution.require_current(packet)
        if pins(packet, repo) != lease["spec"]["pins"]:
            raise SupervisorError("update inputs changed during execution")
        _write_json_atomic(result_path, {
            "schema": 1, "complete": True, "kind": "update-execution",
            "job_id": job_id, "attempt": attempt, "packet_sha256": digest,
            "pins": lease["spec"]["pins"],
            "native_result_sha256": file_sha256(native_path),
            "oracle_result_sha256": file_sha256(oracle_path),
            "native_trace_sha256": file_sha256(native_trace),
            "oracle_trace_sha256": file_sha256(oracle_trace),
            "oracle_vi_trace_sha256": file_sha256(oracle_vi_trace)
                if oracle_vi_trace.is_file() else None,
            "comparison_sha256": file_sha256(report_path),
            "input_poll_comparison_sha256": file_sha256(poll_path),
            "compared_polls": poll_report["shared_prefix_polls"],
            "input_prefix_match": poll_report["first_input_mismatch"] is None,
            "focus_comparison_sha256": file_sha256(focus_path)
                if focus_path.is_file() else None,
            "focus_snapshot_sha256": focus_snapshots,
            **({"entry_trace_sha256": entry_traces} if "entry_probe" in packet else {}),
            **({"point_trace_sha256": point_traces} if "point_probe" in packet else {}),
            "alignment_diagnostic_sha256": file_sha256(alignment_path)
                if alignment_path.is_file() else None,
            "alignment_classification": alignment_classification,
            "compared_updates": report["compared_updates"],
            "prefix_match": report["match"], "first_divergence": report["first_divergence"],
            "parity_verified": False,
        })
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, result_path)
        store.pass_job(job_id, token)
        return f"{job_id}: completed-update prefix sealed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        _write_json_atomic(result_path, {
            "schema": 1, "complete": False, "kind": "update-execution",
            "job_id": job_id, "attempt": attempt, "stop_reason": str(error)[:300],
        })
        try:
            store.fail_job(job_id, token, str(error)[:300],
                           blocked=isinstance(error, SupervisorError))
        except JobStoreError:
            pass
        return f"{job_id}: update comparison blocked ({error})"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    parser.add_argument("--state", type=Path, default=root / "tools/private/autonomy")
    parser.add_argument("--from-job", required=True,
                        help="sealed alignment or update job supplying the selected input")
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--execution-profile", choices=execution.PROFILES, required=True)
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-build", type=Path,
                        help="sealed private snapshot build record for this executable")
    args = parser.parse_args()
    state = args.state.resolve()
    if not state.is_relative_to(root / "tools/private"):
        raise ValueError("update ledger must remain in private storage")
    if (state / "PAUSED").exists():
        raise ValueError("update ledger is paused")
    with JobStore(state / "jobs.sqlite") as store:
        parent = store.job(args.from_job)
        if parent["state"] != "passed" or not parent["sealed_artifact"]:
            raise ValueError("update predecessor must be passed and sealed")
        sealed = Path(parent["sealed_artifact"]).resolve(strict=True)
        if (not sealed.is_relative_to(state / "attempts" / args.from_job) or
                file_sha256(sealed) != parent["sealed_sha256"]):
            raise ValueError("update predecessor seal changed")
        inputs = parent["spec"]["inputs"]
        prefix = inputs[0].split(":", 1)[0] if len(inputs) == 1 else ""
        if prefix not in ("alignment-packet", "update-packet"):
            raise ValueError("update predecessor must supply alignment or update inputs")
        directory = "alignment-packets" if prefix == "alignment-packet" else "update-packets"
        inherited = json.loads((state / directory / (args.from_job + ".json")).read_text())
        report = json.loads(sealed.read_text(encoding="utf-8"))
        if (inputs != [prefix + ":" + hashlib.sha256(canonical_bytes(inherited)).hexdigest()] or
                report.get("complete") is not True or
                report.get("pins") != parent["spec"]["pins"] or
                report.get("packet_sha256") != inputs[0].split(":", 1)[1]):
            raise ValueError("update predecessor packet/report changed")
        pin_files = {**inherited["pin_files"],
                     "native": str(args.native.resolve(strict=True)),
                     "emulator": str(args.emulator.resolve(strict=True))}
        if file_sha256(Path(pin_files["rom"])) != parent["spec"]["pins"]["rom_sha256"]:
            raise ValueError("update predecessor ROM changed")
        identity = {"parent": args.from_job, "target": args.target,
                    "execution": execution.capture(pin_files, args.execution_profile),
                    "native_sha256": file_sha256(Path(pin_files["native"])),
                    "tool_sha256": tool_sha256(root)}
        binding = source_build.pin(args.source_build) if args.source_build else inherited.get("source_build")
        if binding is not None:
            source_build.validate(root, binding, Path(pin_files["native"]))
            identity["source_build"] = binding
        job_id = "execution-update-" + hashlib.sha256(canonical_bytes(identity)).hexdigest()[:24]
        queue_update(store, root, state, job_id=job_id,
                     alignment_id=inherited.get("alignment_id", args.from_job),
                     alignment_result=sealed,
                     alignment_packet={**inherited, "pin_files": pin_files},
                     native_target=args.target,
                     predecessor_id=args.from_job if prefix == "update-packet" else None,
                     execution_profile=args.execution_profile, build_binding=binding)
        status = store.job(job_id)["state"]
    print(json.dumps({"job_id": job_id, "state": status}), flush=True)
    if args.execute and status == "queued":
        from scripts.autonomy.supervisor import run_once
        print(run_once(root, state, args.native.resolve(), require_auth=False,
                       allow_agent=False, job_id=job_id), flush=True)


if __name__ == "__main__":
    main()
