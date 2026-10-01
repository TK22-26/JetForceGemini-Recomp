"""Ledger-backed, model-free controller/update/VI event-order capture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from scripts.autonomy.job_store import ID_RE, SHA256_RE, JobSpec, JobStore, JobStoreError
from scripts.autonomy.poll_lag_job import _context as pair_context
from scripts.autonomy.poll_lag_job import validate as validate_lag_packet
from scripts.autonomy.process_guard import real_python_executable
from scripts.autonomy.supervisor import (
    PIN_FILES, SupervisorError, _git_ok, _inside, _write_json_atomic,
    bounded_command, canonical_bytes, expired_attempt_contained, file_sha256,
)
from scripts import phase9_event_pair as pair
from scripts.phase9_event_trace import validate_windows
from scripts.phase9_controller_callers import analyze as analyze_callers


TOOL_FILES = (
    "scripts/autonomy/atomic_file.py",
    "scripts/autonomy/event_pair_job.py", "scripts/autonomy/supervisor.py",
    "scripts/autonomy/poll_lag_job.py", "scripts/autonomy/job_store.py",
    "scripts/autonomy/process_guard.py", "scripts/phase9_event_pair.py",
    "scripts/phase9_event_trace.py", "scripts/phase9_poll_semantic_pair.py",
    "scripts/phase9_controller_callers.py",
    "scripts/phase9_update_alignment.py",
    "scripts/phase95_native_replay.py", "scripts/phase95_oracle_replay.py",
    "scripts/phase9_oracle_instruction_effects.py",
    "scripts/phase9_point_probe.py",
    "scripts/phase9_bizhawk_oracle.lua", "scripts/compare_phase9_poll_hashes.py",
    "scripts/compare_phase9_update_hashes.py", "scripts/phase95_bridge.py",
    "scripts/build_phase9_route_replays.py", "src/boot/native_boot.cpp",
)
CAPABILITY_MARKER = b"JFG_PHASE9_EVENT_TRACE_RANGE"


def tool_sha256(repo: Path) -> str:
    digest = hashlib.sha256()
    for relative in TOOL_FILES:
        digest.update(relative.encode("ascii"))
        digest.update(bytes.fromhex(file_sha256(repo / relative)))
    return digest.hexdigest()


def event_capable(executable: Path) -> bool:
    """Require the compiled opt-in trace hook before enqueueing a capture."""
    tail = b""
    with Path(executable).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            joined = tail + chunk
            if CAPABILITY_MARKER in joined:
                return True
            tail = joined[-(len(CAPABILITY_MARKER) - 1):]
    return False


def derive_windows(report: dict) -> tuple[tuple[int, int], ...]:
    """Select the first mismatch and first unmatched-poll timing windows."""
    count = report.get("compared_polls")
    mismatch = report.get("mismatch_windows")
    unmatched = report.get("first_unmatched_polls")
    if (type(count) is not int or count < 16 or
            not isinstance(mismatch, list) or not mismatch or
            not isinstance(mismatch[0], dict) or
            type(mismatch[0].get("first_poll")) is not int or
            not isinstance(unmatched, list) or
            any(type(value) is not int for value in unmatched)):
        raise SupervisorError("poll-lag report cannot select event windows")
    first_poll = mismatch[0]["first_poll"]
    if not 0 <= first_poll < count:
        raise SupervisorError("first mismatching poll exceeds the shared prefix")
    first = (max(0, first_poll - 3), min(count - 1, first_poll + 5))
    windows = [first]
    if unmatched:
        anchor = unmatched[0]
        if not 0 <= anchor < count:
            raise SupervisorError("first unmatched poll exceeds the shared prefix")
        if anchor > first[1]:
            second = (max(first[1] + 1, anchor - 4),
                      min(count - 1, anchor + 7))
            if second[0] <= second[1]:
                windows.append(second)
    return validate_windows(windows, poll_hashes=True, update_hashes=True)


def job_id_for(lag_id: str, windows: tuple[tuple[int, int], ...],
               tool_sha: str, native_sha: str) -> str:
    digest = hashlib.sha256(canonical_bytes({
        "lag_id": lag_id, "event_windows": windows,
        "tool_sha256": tool_sha, "native_sha256": native_sha,
    })).hexdigest()[:24]
    return "event-pair-" + digest


def _context(store: JobStore, repo: Path, state: Path, lag_id: str) -> dict:
    lag = store.job(lag_id)
    if (lag["state"] != "passed" or not lag["spec"]["inputs"] or
            not lag["spec"]["inputs"][0].startswith("poll-lag-packet:") or
            not lag["sealed_artifact"] or not lag["sealed_sha256"]):
        raise SupervisorError("event predecessor is not a sealed poll-lag job")
    packet_path = state / "poll-lag-packets" / (lag_id + ".json")
    lag_packet = json.loads(packet_path.read_text(encoding="utf-8"))
    validate_lag_packet(lag_packet, repo, state)
    predecessor = pair_context(store, state, lag_packet["pair_job_id"])
    sealed = Path(lag["sealed_artifact"]).resolve(strict=True)
    report_path = sealed.parent / "lag-report.json"
    if (not sealed.is_relative_to((state / "attempts" / lag_id).resolve()) or
            sealed.name != "result.json" or
            file_sha256(sealed) != lag["sealed_sha256"] or
            not report_path.is_file()):
        raise SupervisorError("event predecessor seal changed")
    result = json.loads(sealed.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    packet_sha = hashlib.sha256(canonical_bytes(lag_packet)).hexdigest()
    if (lag["spec"]["inputs"] != ["poll-lag-packet:" + packet_sha] or
            lag["spec"]["prerequisites"] != [lag_packet["pair_job_id"]] or
            result.get("kind") != "poll-lag-execution" or
            result.get("complete") is not True or
            result.get("job_id") != lag_id or
            result.get("packet_sha256") != packet_sha or
            result.get("pins") != lag["spec"]["pins"] or
            result.get("lag_report_sha256") != file_sha256(report_path) or
            report.get("kind") != "jfg-phase9-poll-lag-analysis" or
            report.get("alignment_validated") is not False or
            report.get("parity_verified") is not False or
            type(report.get("mismatching_polls")) is not int or
            report["mismatching_polls"] < 1 or
            report.get("comparison_sha256") != file_sha256(
                predecessor["pair_root"] / "comparison.json") or
            any(report.get(key) != result.get(key) for key in (
                "mismatching_polls", "unique_shift_match",
                "ambiguous_shift_match", "no_shift_match"))):
        raise SupervisorError("event predecessor result is inconsistent")
    native = Path(predecessor["packet"]["pin_files"]["native"])
    if (not native.is_file() or
            file_sha256(native) != predecessor["job"]["spec"]["pins"]["native_sha256"]):
        raise SupervisorError("poll-pair native executable changed")
    return {"lag": lag, "lag_packet": lag_packet, "lag_seal": sealed,
            "lag_report_path": report_path, "report": report,
            "pair": predecessor}


def pins(packet: dict, repo: Path) -> dict[str, str]:
    return {"source_commit": packet["source_commit"],
            "tool_sha256": tool_sha256(repo),
            **{key + "_sha256": file_sha256(Path(packet["pin_files"][key]))
               for key in PIN_FILES}}


def validate(packet: dict, repo: Path, state: Path) -> None:
    required = {"schema", "job_id", "lag_id", "pair_id", "source_commit",
                "pin_files", "source_export", "target", "timeout_seconds",
                "event_windows", "evidence_files"}
    if (not isinstance(packet, dict) or set(packet) != required or
            packet["schema"] != 1 or
            any(not isinstance(packet[key], str) or not ID_RE.fullmatch(packet[key])
                for key in ("job_id", "lag_id", "pair_id"))):
        raise SupervisorError("invalid event-pair packet")
    commit = packet["source_commit"]
    if (not isinstance(commit, str) or
            _git_ok(repo, "rev-parse", "--verify", commit + "^{commit}") != commit):
        raise SupervisorError("event-pair source commit is not pinned")
    if not isinstance(packet["pin_files"], dict) or \
            set(packet["pin_files"]) != set(PIN_FILES):
        raise SupervisorError("event-pair binary pins are incomplete")
    for key in PIN_FILES:
        value = packet["pin_files"][key]
        if not isinstance(value, str) or not Path(value).is_absolute() or \
                not Path(value).is_file():
            raise SupervisorError(f"event-pair {key} pin is missing")
    source = Path(packet["source_export"])
    if (not source.is_absolute() or not source.is_dir() or
            not _inside(source, repo / "tools" / "private") or
            type(packet["target"]) is not int or not 120 <= packet["target"] <= 100000 or
            type(packet["timeout_seconds"]) is not int or
            not 60 <= packet["timeout_seconds"] <= 1800):
        raise SupervisorError("event-pair source or target is invalid")
    try:
        windows = validate_windows(packet["event_windows"], poll_hashes=True,
                                   update_hashes=True)
    except ValueError as error:
        raise SupervisorError(str(error)) from error
    if not windows or windows[-1][1] >= packet["target"]:
        raise SupervisorError("event-pair windows exceed the capture target")
    evidence = packet["evidence_files"]
    if not isinstance(evidence, list) or len(evidence) != 14:
        raise SupervisorError("event-pair evidence list is incomplete")
    for item in evidence:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"} or
                not isinstance(item["path"], str) or
                not isinstance(item["sha256"], str) or
                not SHA256_RE.fullmatch(item["sha256"])):
            raise SupervisorError("invalid event-pair evidence pin")
        path = Path(item["path"])
        if (not path.is_absolute() or not path.is_file() or
                not _inside(path, repo / "tools" / "private") or
                file_sha256(path) != item["sha256"]):
            raise SupervisorError("event-pair evidence changed")


def queue(store: JobStore, repo: Path, state: Path, lag_id: str,
          *, timeout: int = 600) -> str:
    context = _context(store, repo, state, lag_id)
    pair_job = context["pair"]
    pair_packet = pair_job["packet"]
    native = Path(pair_packet["pin_files"]["native"])
    if not event_capable(native):
        raise SupervisorError("pinned native binary lacks event trace support")
    windows = derive_windows(context["report"])
    target = pair_packet["target"]
    if windows[-1][1] >= target:
        raise SupervisorError("event windows exceed sealed poll-pair target")
    if type(timeout) is not int or not 60 <= timeout <= 1800:
        raise SupervisorError("event-pair timeout must be 60..1800 seconds")
    job_id = job_id_for(lag_id, windows, tool_sha256(repo),
                        pair_job["job"]["spec"]["pins"]["native_sha256"])
    files = [context["lag_seal"], context["lag_report_path"],
             *pair_job["files"]]
    packet = {"schema": 1, "job_id": job_id, "lag_id": lag_id,
              "pair_id": pair_packet["job_id"],
              "source_commit": _git_ok(repo, "rev-parse", "HEAD"),
              "pin_files": pair_packet["pin_files"],
              "source_export": str(pair_job["source"]),
              "target": target, "timeout_seconds": timeout,
              "event_windows": windows,
              "evidence_files": [
                  {"path": str(path), "sha256": file_sha256(path)}
                  for path in files]}
    validate(packet, repo, state)
    encoded = canonical_bytes(packet)
    directory = state / "event-pair-packets"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (job_id + ".json")
    if path.exists() and path.read_bytes() != encoded:
        raise SupervisorError("event-pair ID already names another packet")
    if not path.exists():
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
    store.enqueue(JobSpec(job_id, pins(packet, repo),
                          ("event-pair-packet:" + hashlib.sha256(encoded).hexdigest(),),
                          (lag_id,), "emulator:bizhawk", 1, "json_complete"))
    return job_id


def _complete_pair(attempt_dir: Path, packet: dict, lease: dict) -> dict | None:
    output = attempt_dir / "pair"
    if not all((output / relative).is_file() for relative in (
            "plan.json", "pair-result.json", "comparison.json",
            "event-report.json", "update-alignment.json",
            "native/native-result.json",
            "oracle/oracle-result.json")):
        return None
    summary = pair.run(
        output, Path(packet["source_export"]),
        Path(packet["pin_files"]["native"]),
        Path(packet["pin_files"]["emulator"]),
        Path(packet["pin_files"]["rom"]),
        lease["spec"]["pins"]["rom_sha256"],
        target=packet["target"], timeout=packet["timeout_seconds"],
        event_windows=packet["event_windows"])
    report = json.loads((output / "event-report.json").read_text(
        encoding="utf-8"))
    updates = json.loads((output / "update-alignment.json").read_text(
        encoding="utf-8"))
    if (summary.get("complete") is not True or
            summary.get("alignment_validated") is not False or
            summary.get("parity_verified") is not False or
            summary.get("event_report_sha256") != file_sha256(
                output / "event-report.json") or
            summary.get("update_alignment_sha256") != file_sha256(
                output / "update-alignment.json") or
            summary.get("matching_update_prefix") != updates.get(
                "matching_update_prefix") or
            updates.get("kind") != "jfg-phase9-update-alignment" or
            updates.get("alignment_validated") is not False or
            updates.get("parity_verified") is not False or
            report.get("first_input_mismatch_poll") is not None or
            report.get("alignment_validated") is not False or
            report.get("parity_verified") is not False):
        raise SupervisorError("event-pair diagnostic is not complete")
    return {"pair_result_sha256": file_sha256(output / "pair-result.json"),
            "event_report_sha256": file_sha256(output / "event-report.json"),
            "update_alignment_sha256": file_sha256(
                output / "update-alignment.json"),
            "comparison_sha256": file_sha256(output / "comparison.json"),
            "shared_polls": summary["shared_polls"],
            "first_event_interval_difference": summary[
                "first_event_interval_difference"]}


def sealed_context(store: JobStore, repo: Path, state: Path,
                   event_id: str) -> dict:
    """Read-only verification for downstream diagnoses; never recapture."""
    job = store.job(event_id)
    if (job["state"] != "passed" or not job["spec"]["inputs"] or
            not job["spec"]["inputs"][0].startswith("event-pair-packet:") or
            not job["sealed_artifact"] or not job["sealed_sha256"]):
        raise SupervisorError("event pair is not sealed")
    packet = json.loads((state / "event-pair-packets" /
                         (event_id + ".json")).read_text(encoding="utf-8"))
    validate(packet, repo, state)
    packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    sealed = Path(job["sealed_artifact"]).resolve(strict=True)
    root = (state / "attempts" / event_id).resolve()
    if (not sealed.is_relative_to(root) or sealed.name != "result.json" or
            file_sha256(sealed) != job["sealed_sha256"] or
            job["spec"]["inputs"] != ["event-pair-packet:" + packet_sha] or
            job["spec"]["prerequisites"] != [packet["lag_id"]]):
        raise SupervisorError("sealed event pair identity changed")
    result = json.loads(sealed.read_text(encoding="utf-8"))
    pair_root = Path(result.get("pair_root", "")).resolve(strict=True)
    if (pair_root.name != "pair" or not pair_root.is_relative_to(root) or
            result.get("complete") is not True or
            result.get("kind") != "event-pair-execution" or
            result.get("job_id") != event_id or
            result.get("packet_sha256") != packet_sha or
            result.get("pins") != job["spec"]["pins"] or
            result.get("alignment_validated") is not False or
            result.get("parity_verified") is not False):
        raise SupervisorError("sealed event pair result changed")
    plan_path = pair_root / "plan.json"
    pair_result_path = pair_root / "pair-result.json"
    report_path = pair_root / "event-report.json"
    comparison_path = pair_root / "comparison.json"
    update_alignment_path = pair_root / "update-alignment.json"
    native_trace = pair_root / "native" / "retrace-hashes.jsonl.events.tsv"
    oracle_trace = pair_root / "oracle" / "events.tsv"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    summary = json.loads(pair_result_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (plan.get("kind") != pair.KIND or
            plan.get("target") != packet["target"] or
            plan.get("source_export") != packet["source_export"] or
            plan.get("event_windows") != packet["event_windows"] or
            any(plan.get(key + "_sha256") != job["spec"]["pins"][key + "_sha256"]
                for key in ("rom", "emulator")) or
            plan.get("native_executable_sha256") !=
                job["spec"]["pins"]["native_sha256"] or
            summary.get("kind") != pair.KIND or
            summary.get("complete") is not True or
            summary.get("alignment_validated") is not False or
            summary.get("parity_verified") is not False or
            summary.get("plan_sha256") != file_sha256(plan_path) or
            summary.get("event_report_sha256") != file_sha256(report_path) or
            summary.get("comparison_sha256") != file_sha256(comparison_path) or
            (summary.get("update_alignment_sha256") is not None and
             (summary["update_alignment_sha256"] !=
              file_sha256(update_alignment_path) or
              result.get("update_alignment_sha256") !=
              file_sha256(update_alignment_path))) or
            summary.get("native_event_trace_sha256") != file_sha256(native_trace) or
            summary.get("oracle_event_trace_sha256") != file_sha256(oracle_trace) or
            result.get("pair_result_sha256") != file_sha256(pair_result_path) or
            result.get("event_report_sha256") != file_sha256(report_path) or
            result.get("comparison_sha256") != file_sha256(comparison_path) or
            report.get("kind") != "jfg-phase9-event-order-diagnostic" or
            report.get("native_trace_sha256") != file_sha256(native_trace) or
            report.get("oracle_trace_sha256") != file_sha256(oracle_trace) or
            report.get("first_input_mismatch_poll") is not None or
            report.get("alignment_validated") is not False or
            report.get("parity_verified") is not False):
        raise SupervisorError("sealed event pair evidence is inconsistent")
    caller_report_path = pair_root / "controller-caller-report.json"
    caller_trace = pair_root / "oracle" / "controller-callers.tsv"
    caller_report = None
    if summary.get("controller_caller_report_sha256") is not None:
        if (summary["controller_caller_report_sha256"] !=
                file_sha256(caller_report_path) or
                summary.get("controller_caller_trace_sha256") !=
                file_sha256(caller_trace)):
            raise SupervisorError("sealed controller caller digest changed")
        caller_report = json.loads(caller_report_path.read_text(
            encoding="utf-8"))
        if caller_report != analyze_callers(
                caller_trace, tuple(tuple(w) for w in packet["event_windows"])):
            raise SupervisorError("sealed controller caller report changed")
    return {"job": job, "packet": packet, "sealed": sealed,
            "pair_root": pair_root, "report": report,
            "report_path": report_path, "native_trace": native_trace,
            "oracle_trace": oracle_trace,
            "caller_report": caller_report,
            "caller_report_path": caller_report_path if caller_report else None,
            "update_alignment_path": (update_alignment_path
                                      if summary.get("update_alignment_sha256")
                                      is not None else None)}


def run_lease(store: JobStore, lease: dict, repo: Path, state: Path) -> str:
    job_id, token, attempt = lease["job_id"], lease["token"], lease["attempt"]
    attempt_dir = state / "attempts" / job_id / f"{attempt:04d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    result_path = attempt_dir / "result.json"
    try:
        packet = json.loads((state / "event-pair-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        validate(packet, repo, state)
        packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (lease["spec"]["inputs"] != ["event-pair-packet:" + packet_sha] or
                lease["spec"]["prerequisites"] != [packet["lag_id"]] or
                pins(packet, repo) != lease["spec"]["pins"]):
            raise SupervisorError("event-pair packet or tool pins changed")
        context = _context(store, repo, state, packet["lag_id"])
        pair_job = context["pair"]
        expected = [context["lag_seal"], context["lag_report_path"],
                    *pair_job["files"]]
        if (packet["pair_id"] != pair_job["packet"]["job_id"] or
                packet["pin_files"] != pair_job["packet"]["pin_files"] or
                packet["source_export"] != str(pair_job["source"]) or
                packet["target"] != pair_job["packet"]["target"] or
                packet["job_id"] != job_id_for(
                    packet["lag_id"], derive_windows(context["report"]),
                    tool_sha256(repo), lease["spec"]["pins"]["native_sha256"]) or
                tuple(tuple(window) for window in packet["event_windows"]) !=
                derive_windows(context["report"]) or
                packet["evidence_files"] != [
                    {"path": str(path), "sha256": file_sha256(path)}
                    for path in expected]):
            raise SupervisorError("event-pair predecessor evidence changed")
        for previous in store.attempt_history(job_id):
            if previous["number"] >= attempt or previous["outcome"] != "expired":
                continue
            prior = state / "attempts" / job_id / f"{previous['number']:04d}"
            if not expired_attempt_contained(prior):
                raise SupervisorError("expired event-pair worker may still be live")
            recovered = _complete_pair(prior, packet, lease)
            if recovered is not None:
                _write_json_atomic(result_path, {
                    "schema": 1, "complete": True, "kind": "event-pair-execution",
                    "job_id": job_id, "attempt": attempt,
                    "recovered_from_attempt": previous["number"],
                    "pair_root": str(prior / "pair"),
                    "packet_sha256": packet_sha, "pins": lease["spec"]["pins"],
                    "alignment_validated": False, "parity_verified": False,
                    **recovered})
                store.start(job_id, token)
                store.verify(job_id, token)
                store.seal_artifact(job_id, token, result_path)
                store.pass_job(job_id, token)
                return f"{job_id}: prior event pair recovered"
        store.start(job_id, token)
        command = [real_python_executable(), "-m", "scripts.phase9_event_pair",
                   str(attempt_dir / "pair"), "--source", packet["source_export"],
                   "--executable", packet["pin_files"]["native"],
                   "--emulator", packet["pin_files"]["emulator"],
                   "--rom", packet["pin_files"]["rom"],
                   "--rom-sha256", lease["spec"]["pins"]["rom_sha256"],
                   "--target", str(packet["target"]),
                   "--timeout", str(packet["timeout_seconds"])]
        for first, last in packet["event_windows"]:
            command.extend(("--window", f"{first}:{last}"))
        code, reason = bounded_command(
            command, repo, attempt_dir / "pair.stdout", attempt_dir / "pair.stderr",
            time.monotonic() + 2 * packet["timeout_seconds"] + 60,
            lambda: store.heartbeat(job_id, token, ttl=120), state / "PAUSED",
            guard_record=attempt_dir / "pair.guard.json",
            cpu_seconds=2 * packet["timeout_seconds"] + 60)
        if code != 0 or reason is not None:
            raise RuntimeError(f"bounded event-pair worker failed: {reason or code}")
        complete = _complete_pair(attempt_dir, packet, lease)
        if complete is None:
            raise SupervisorError("event-pair worker produced no complete bundle")
        validate(packet, repo, state)
        if pins(packet, repo) != lease["spec"]["pins"]:
            raise SupervisorError("event-pair pins changed during capture")
        _write_json_atomic(result_path, {
            "schema": 1, "complete": True, "kind": "event-pair-execution",
            "job_id": job_id, "attempt": attempt,
            "pair_root": str(attempt_dir / "pair"),
            "packet_sha256": packet_sha, "pins": lease["spec"]["pins"],
            "alignment_validated": False, "parity_verified": False,
            **complete})
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, result_path)
        store.pass_job(job_id, token)
        return f"{job_id}: event pair sealed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        _write_json_atomic(result_path, {
            "schema": 1, "complete": False, "kind": "event-pair-execution",
            "job_id": job_id, "attempt": attempt,
            "stop_reason": str(error)[:300]})
        try:
            store.fail_job(job_id, token, str(error)[:300],
                           blocked=isinstance(error, SupervisorError))
        except JobStoreError:
            pass
        return f"{job_id}: event pair blocked ({error})"
