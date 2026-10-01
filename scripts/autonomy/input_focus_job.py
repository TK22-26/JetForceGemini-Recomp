"""Ledger successor for model-free game-visible controller input comparison."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from scripts.autonomy.event_pair_job import sealed_context as event_context
from scripts.autonomy.job_store import ID_RE, SHA256_RE, JobSpec, JobStore, JobStoreError
from scripts.autonomy.process_guard import real_python_executable
from scripts.autonomy.supervisor import (
    PIN_FILES, SupervisorError, _git_ok, _inside, _write_json_atomic,
    bounded_command, canonical_bytes, expired_attempt_contained, file_sha256,
)
from scripts import phase9_update_focus_pair as focus_pair
from scripts.phase9_update_alignment import analyze as analyze_updates


TOOL_FILES = (
    "scripts/autonomy/atomic_file.py",
    "scripts/autonomy/input_focus_job.py", "scripts/autonomy/event_pair_job.py",
    "scripts/autonomy/supervisor.py", "scripts/autonomy/job_store.py",
    "scripts/autonomy/process_guard.py", "scripts/phase9_update_focus_pair.py",
    "scripts/phase9_update_alignment.py", "scripts/phase9_poll_semantic_pair.py",
    "scripts/phase95_native_replay.py", "scripts/phase95_oracle_replay.py",
    "scripts/phase9_oracle_instruction_effects.py",
    "scripts/phase9_point_probe.py",
    "scripts/phase9_bizhawk_oracle.lua", "scripts/compare_phase9_update_hashes.py",
    "scripts/phase95_bridge.py", "src/boot/native_boot.cpp",
)


def tool_sha256(repo: Path) -> str:
    value = hashlib.sha256()
    for relative in TOOL_FILES:
        value.update(relative.encode("ascii"))
        value.update(bytes.fromhex(file_sha256(repo / relative)))
    return value.hexdigest()


def job_id_for(event_id: str, focus: tuple[int, int], tool_sha: str,
               native_sha: str) -> str:
    value = hashlib.sha256(canonical_bytes({
        "event_id": event_id, "focus_updates": focus,
        "tool_sha256": tool_sha, "native_sha256": native_sha,
    })).hexdigest()[:24]
    return "input-focus-" + value


def _context(store: JobStore, repo: Path, state: Path,
             event_id: str) -> dict:
    event = event_context(store, repo, state, event_id)
    root = event["pair_root"]
    alignment = analyze_updates(
        root / "native" / "retrace-hashes.jsonl.updates.jsonl",
        root / "oracle" / "update-hashes.jsonl")
    focus = focus_pair.focus_range(alignment)
    plan = json.loads((root / "plan.json").read_text(encoding="utf-8"))
    native = Path(event["packet"]["pin_files"]["native"])
    if (not native.is_file() or
            file_sha256(native) !=
            event["job"]["spec"]["pins"]["native_sha256"] or
            plan.get("target") != event["packet"]["target"] or
            focus[1] >= plan["target"]):
        raise SupervisorError("event focus native pin or target changed")
    return {"event": event, "alignment": alignment, "focus": focus,
            "plan": plan}


def pins(packet: dict, repo: Path) -> dict[str, str]:
    return {"source_commit": packet["source_commit"],
            "tool_sha256": tool_sha256(repo),
            **{key + "_sha256": file_sha256(
                Path(packet["pin_files"][key])) for key in PIN_FILES}}


def _evidence(context: dict) -> list[Path]:
    event = context["event"]
    root = event["pair_root"]
    source = Path(context["plan"]["source_export"])
    return [event["sealed"], root / "plan.json", root / "pair-result.json",
            root / "native" / "retrace-hashes.jsonl.updates.jsonl",
            root / "oracle" / "update-hashes.jsonl",
            source / "controller.input", source / "initial.flash",
            source / "initial.pak"]


def validate(packet: dict, repo: Path, state: Path) -> None:
    required = {"schema", "job_id", "event_id", "source_commit",
                "pin_files", "focus_updates", "timeout_seconds",
                "evidence_files"}
    if (not isinstance(packet, dict) or set(packet) != required or
            packet["schema"] != 1 or
            any(not isinstance(packet[key], str) or not ID_RE.fullmatch(
                packet[key]) for key in ("job_id", "event_id")) or
            not isinstance(packet["source_commit"], str) or
            _git_ok(repo, "rev-parse", "--verify",
                    packet["source_commit"] + "^{commit}") !=
            packet["source_commit"] or
            not isinstance(packet["pin_files"], dict) or
            set(packet["pin_files"]) != set(PIN_FILES) or
            type(packet["timeout_seconds"]) is not int or
            not 60 <= packet["timeout_seconds"] <= 1800 or
            not isinstance(packet["focus_updates"], list) or
            len(packet["focus_updates"]) != 2 or
            any(type(value) is not int for value in packet["focus_updates"]) or
            not 1 <= packet["focus_updates"][0] <=
            packet["focus_updates"][1] or
            packet["focus_updates"][1] -
            packet["focus_updates"][0] > 15):
        raise SupervisorError("invalid input-focus packet")
    for key in PIN_FILES:
        value = packet["pin_files"][key]
        if not isinstance(value, str) or not Path(value).is_absolute() or \
                not Path(value).is_file():
            raise SupervisorError("input-focus binary pin is missing")
    evidence = packet["evidence_files"]
    if not isinstance(evidence, list) or len(evidence) != 8:
        raise SupervisorError("input-focus evidence list is incomplete")
    for item in evidence:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"} or
                not isinstance(item["path"], str) or
                not isinstance(item["sha256"], str) or
                not SHA256_RE.fullmatch(item["sha256"])):
            raise SupervisorError("invalid input-focus evidence pin")
        path = Path(item["path"])
        if (not path.is_absolute() or not path.is_file() or
                not _inside(path, repo / "tools" / "private") or
                file_sha256(path) != item["sha256"]):
            raise SupervisorError("input-focus evidence changed")


def queue(store: JobStore, repo: Path, state: Path, event_id: str,
          *, timeout: int = 600) -> str:
    context = _context(store, repo, state, event_id)
    if type(timeout) is not int or not 60 <= timeout <= 1800:
        raise SupervisorError("input-focus timeout must be 60..1800 seconds")
    native_sha = context["event"]["job"]["spec"]["pins"]["native_sha256"]
    job_id = job_id_for(event_id, context["focus"], tool_sha256(repo),
                        native_sha)
    packet = {
        "schema": 1, "job_id": job_id, "event_id": event_id,
        "source_commit": _git_ok(repo, "rev-parse", "HEAD"),
        "pin_files": context["event"]["packet"]["pin_files"],
        "focus_updates": list(context["focus"]),
        "timeout_seconds": timeout,
        "evidence_files": [
            {"path": str(path), "sha256": file_sha256(path)}
            for path in _evidence(context)],
    }
    validate(packet, repo, state)
    encoded = canonical_bytes(packet)
    directory = state / "input-focus-packets"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (job_id + ".json")
    if path.exists() and path.read_bytes() != encoded:
        raise SupervisorError("input-focus ID already names another packet")
    if not path.exists():
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
    store.enqueue(JobSpec(job_id, pins(packet, repo),
                          ("input-focus-packet:" +
                           hashlib.sha256(encoded).hexdigest(),),
                          (event_id,), "emulator:bizhawk", 1,
                          "json_complete"))
    return job_id


def _complete(attempt_dir: Path, packet: dict, lease: dict) -> dict | None:
    output = attempt_dir / "pair"
    if not all((output / relative).is_file() for relative in (
            "plan.json", "pair-result.json", "focus-input-report.json",
            "native/native-result.json", "oracle/oracle-result.json")):
        return None
    result = focus_pair.run(output, Path(packet["evidence_files"][1]["path"]).parent,
                            timeout=packet["timeout_seconds"])
    report_path = output / "focus-input-report.json"
    if (result.get("complete") is not True or
            result.get("alignment_validated") is not False or
            result.get("parity_verified") is not False or
            result.get("focus_input_report_sha256") != file_sha256(
                report_path) or
            [result.get("first_update"), result.get("last_update")] !=
            packet["focus_updates"]):
        raise SupervisorError("input-focus worker did not produce a complete pair")
    return {"pair_result_sha256": file_sha256(output / "pair-result.json"),
            "focus_input_report_sha256": file_sha256(report_path),
            "first_input_buffer_difference_update": result[
                "first_input_buffer_difference_update"]}


def sealed_context(store: JobStore, repo: Path, state: Path,
                   job_id: str) -> dict:
    job = store.job(job_id)
    if (job["state"] != "passed" or not job["sealed_artifact"] or
            not job["sealed_sha256"]):
        raise SupervisorError("input-focus pair is not sealed")
    packet_path = state / "input-focus-packets" / (job_id + ".json")
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    validate(packet, repo, state)
    packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    sealed = Path(job["sealed_artifact"]).resolve(strict=True)
    root = (state / "attempts" / job_id).resolve()
    if (not sealed.is_relative_to(root) or sealed.name != "result.json" or
            file_sha256(sealed) != job["sealed_sha256"] or
            job["spec"]["inputs"] != ["input-focus-packet:" + packet_sha] or
            job["spec"]["prerequisites"] != [packet["event_id"]]):
        raise SupervisorError("sealed input-focus identity changed")
    result = json.loads(sealed.read_text(encoding="utf-8"))
    pair_root = Path(result.get("pair_root", "")).resolve(strict=True)
    report_path = pair_root / "focus-input-report.json"
    pair_result_path = pair_root / "pair-result.json"
    if (pair_root.name != "pair" or not pair_root.is_relative_to(root) or
            result.get("kind") != "input-focus-execution" or
            result.get("complete") is not True or
            result.get("job_id") != job_id or
            result.get("packet_sha256") != packet_sha or
            result.get("pins") != job["spec"]["pins"] or
            result.get("alignment_validated") is not False or
            result.get("parity_verified") is not False or
            result.get("pair_result_sha256") !=
            file_sha256(pair_result_path) or
            result.get("focus_input_report_sha256") !=
            file_sha256(report_path)):
        raise SupervisorError("sealed input-focus evidence changed")
    pair_result = json.loads(pair_result_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    plan_path = pair_root / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    predecessor = event_context(store, repo, state, packet["event_id"])
    alignment = analyze_updates(
        predecessor["pair_root"] / "native" /
        "retrace-hashes.jsonl.updates.jsonl",
        predecessor["pair_root"] / "oracle" / "update-hashes.jsonl")
    predecessor_summary = json.loads((predecessor["pair_root"] /
        "pair-result.json").read_text(encoding="utf-8"))
    alignment_sha = focus_pair.verified_alignment_sha(
        predecessor["pair_root"] / "update-alignment.json", alignment,
        predecessor_summary.get("update_alignment_sha256"))
    recomputed = focus_pair.compare_snapshots(
        pair_root / "native", pair_root / "oracle",
        packet["focus_updates"][0], packet["focus_updates"][1])
    if (pair_result.get("kind") != focus_pair.KIND or
            pair_result.get("complete") is not True or
            pair_result.get("plan_sha256") != file_sha256(plan_path) or
            pair_result.get("native_result_sha256") != file_sha256(
                pair_root / "native" / "native-result.json") or
            pair_result.get("oracle_result_sha256") != file_sha256(
                pair_root / "oracle" / "oracle-result.json") or
            pair_result.get("focus_input_report_sha256") !=
            file_sha256(report_path) or
            plan.get("kind") != focus_pair.KIND or
            plan.get("predecessor") != str(predecessor["pair_root"]) or
            plan.get("predecessor_alignment_sha256") != alignment_sha or
            plan.get("focus_updates") != packet["focus_updates"] or
            plan.get("native_executable_sha256") !=
            job["spec"]["pins"]["native_sha256"] or
            plan.get("rom_sha256") != job["spec"]["pins"]["rom_sha256"] or
            report.get("kind") != "jfg-phase9-update-focus-input-comparison" or
            report != recomputed or
            report.get("alignment_validated") is not False or
            report.get("parity_verified") is not False or
            report.get("first_input_buffer_difference_update") !=
            result.get("first_input_buffer_difference_update")):
        raise SupervisorError("sealed input-focus report is inconsistent")
    return {"job": job, "packet": packet, "sealed": sealed,
            "report_path": report_path, "report": report,
            "pair_root": pair_root, "alignment": alignment}


def run_lease(store: JobStore, lease: dict, repo: Path, state: Path) -> str:
    job_id, token, attempt = lease["job_id"], lease["token"], lease["attempt"]
    attempt_dir = state / "attempts" / job_id / f"{attempt:04d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    result_path = attempt_dir / "result.json"
    try:
        packet = json.loads((state / "input-focus-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        validate(packet, repo, state)
        packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (lease["spec"]["inputs"] != ["input-focus-packet:" + packet_sha] or
                lease["spec"]["prerequisites"] != [packet["event_id"]] or
                pins(packet, repo) != lease["spec"]["pins"]):
            raise SupervisorError("input-focus packet or pins changed")
        context = _context(store, repo, state, packet["event_id"])
        if (list(context["focus"]) != packet["focus_updates"] or
                context["event"]["packet"]["pin_files"] !=
                packet["pin_files"] or
                packet["evidence_files"] != [
                    {"path": str(path), "sha256": file_sha256(path)}
                    for path in _evidence(context)] or
                job_id != job_id_for(
                    packet["event_id"], context["focus"], tool_sha256(repo),
                    lease["spec"]["pins"]["native_sha256"])):
            raise SupervisorError("input-focus predecessor evidence changed")
        for previous in store.attempt_history(job_id):
            if previous["number"] >= attempt or previous["outcome"] != "expired":
                continue
            prior = state / "attempts" / job_id / f"{previous['number']:04d}"
            if not expired_attempt_contained(prior):
                raise SupervisorError("expired input-focus worker may still be live")
            recovered = _complete(prior, packet, lease)
            if recovered is not None:
                _write_json_atomic(result_path, {
                    "schema": 1, "complete": True,
                    "kind": "input-focus-execution", "job_id": job_id,
                    "attempt": attempt,
                    "recovered_from_attempt": previous["number"],
                    "pair_root": str(prior / "pair"),
                    "packet_sha256": packet_sha, "pins": lease["spec"]["pins"],
                    "alignment_validated": False, "parity_verified": False,
                    **recovered})
                store.start(job_id, token)
                store.verify(job_id, token)
                store.seal_artifact(job_id, token, result_path)
                store.pass_job(job_id, token)
                return f"{job_id}: prior input-focus pair recovered"
        store.start(job_id, token)
        command = [real_python_executable(), "-m",
                   "scripts.phase9_update_focus_pair", str(attempt_dir / "pair"),
                   "--event-pair", str(context["event"]["pair_root"]),
                   "--timeout", str(packet["timeout_seconds"])]
        code, reason = bounded_command(
            command, repo, attempt_dir / "pair.stdout", attempt_dir / "pair.stderr",
            time.monotonic() + 2 * packet["timeout_seconds"] + 60,
            lambda: store.heartbeat(job_id, token, ttl=120), state / "PAUSED",
            guard_record=attempt_dir / "pair.guard.json",
            cpu_seconds=2 * packet["timeout_seconds"] + 60)
        if code != 0 or reason is not None:
            raise RuntimeError(f"bounded input-focus worker failed: {reason or code}")
        complete = _complete(attempt_dir, packet, lease)
        if complete is None:
            raise SupervisorError("input-focus worker produced no complete pair")
        validate(packet, repo, state)
        if pins(packet, repo) != lease["spec"]["pins"]:
            raise SupervisorError("input-focus pins changed during capture")
        _write_json_atomic(result_path, {
            "schema": 1, "complete": True,
            "kind": "input-focus-execution", "job_id": job_id,
            "attempt": attempt, "pair_root": str(attempt_dir / "pair"),
            "packet_sha256": packet_sha, "pins": lease["spec"]["pins"],
            "alignment_validated": False, "parity_verified": False,
            **complete})
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, result_path)
        store.pass_job(job_id, token)
        return f"{job_id}: input-focus pair sealed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        _write_json_atomic(result_path, {
            "schema": 1, "complete": False,
            "kind": "input-focus-execution", "job_id": job_id,
            "attempt": attempt, "stop_reason": str(error)[:300]})
        try:
            store.fail_job(job_id, token, str(error)[:300],
                           blocked=isinstance(error, SupervisorError))
        except JobStoreError:
            pass
        return f"{job_id}: input-focus pair blocked ({error})"
