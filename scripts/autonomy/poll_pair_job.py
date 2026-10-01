"""Ledger-backed, model-free native/BizHawk controller-poll comparison."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from scripts.autonomy.determinism_job import _baseline
from scripts.autonomy.job_store import ID_RE, SHA256_RE, JobSpec, JobStore, JobStoreError
from scripts.autonomy.process_guard import real_python_executable
from scripts.autonomy.supervisor import (
    PIN_FILES, SupervisorError, _git_ok, _inside, _write_json_atomic,
    bounded_command, canonical_bytes, expired_attempt_contained, file_sha256,
)
from scripts import phase9_poll_semantic_pair as pair


TOOL_FILES = (
    "scripts/autonomy/atomic_file.py",
    "scripts/autonomy/poll_pair_job.py",
    "scripts/autonomy/supervisor.py",
    "scripts/autonomy/determinism_job.py",
    "scripts/autonomy/update_job.py",
    "scripts/autonomy/controller_return_job.py",
    "scripts/autonomy/event_pair_job.py",
    "scripts/autonomy/job_store.py",
    "scripts/phase9_poll_semantic_pair.py",
    "scripts/compare_phase9_poll_hashes.py",
    "scripts/phase95_native_replay.py",
    "scripts/phase9_point_probe.py",
    "scripts/phase95_oracle_replay.py",
    "scripts/phase9_oracle_instruction_effects.py",
    "scripts/phase9_bizhawk_oracle.lua",
    "scripts/phase95_bridge.py",
    "scripts/compare_phase9_retrace_hashes.py",
    "scripts/compare_phase9_update_hashes.py",
    "scripts/build_phase9_route_replays.py",
    "scripts/autonomy/process_guard.py",
)
INPUT_NAMES = ("export-manifest.json", "controller.input", "initial.flash",
               "initial.pak")


def tool_sha256(repo: Path) -> str:
    digest = hashlib.sha256()
    for relative in TOOL_FILES:
        digest.update(relative.encode("ascii"))
        digest.update(bytes.fromhex(file_sha256(repo / relative)))
    return digest.hexdigest()


def job_id_for(baseline_id: str, target: int, tool_sha: str,
               native_sha: str) -> str:
    key = hashlib.sha256(canonical_bytes({
        "baseline_id": baseline_id, "target": target,
        "tool_sha256": tool_sha, "native_sha256": native_sha,
    })).hexdigest()[:24]
    return "poll-pair-" + key


def pins(packet: dict, repo: Path) -> dict[str, str]:
    return {"source_commit": packet["source_commit"],
            "tool_sha256": tool_sha256(repo),
            **{key + "_sha256": file_sha256(Path(packet["pin_files"][key]))
               for key in PIN_FILES}}


def validate(packet: dict, repo: Path, state: Path) -> None:
    required = {"schema", "job_id", "source_commit", "pin_files",
                "source_export", "target", "timeout_seconds", "evidence_files"}
    predecessor_fields = {"baseline_id", "controller_return_id"}
    if (not isinstance(packet, dict) or
            set(packet) != required | (set(packet) & predecessor_fields) or
            len(set(packet) & predecessor_fields) != 1 or
            packet["schema"] != 1 or
            any(not isinstance(packet.get(key), str) or not ID_RE.fullmatch(packet[key])
                for key in ("job_id", next(iter(set(packet) & predecessor_fields))))):
        raise SupervisorError("invalid poll-pair packet schema or IDs")
    commit = packet["source_commit"]
    if (not isinstance(commit, str) or len(commit) not in (40, 64) or
            _git_ok(repo, "rev-parse", "--verify", commit + "^{commit}") != commit):
        raise SupervisorError("poll-pair source commit is not pinned")
    if not isinstance(packet["pin_files"], dict) or set(packet["pin_files"]) != set(PIN_FILES):
        raise SupervisorError("poll-pair binary pins are incomplete")
    for key in PIN_FILES:
        path = packet["pin_files"][key]
        if not isinstance(path, str) or not Path(path).is_absolute() or not Path(path).is_file():
            raise SupervisorError(f"poll-pair {key} pin file is missing")
    if not isinstance(packet["source_export"], str):
        raise SupervisorError("poll-pair source export is invalid")
    source = Path(packet["source_export"])
    if (not source.is_absolute() or not source.is_dir() or
            not _inside(source, repo / "tools" / "private") or
            type(packet["target"]) is not int or not 120 <= packet["target"] <= 100_000 or
            type(packet["timeout_seconds"]) is not int or
            not 60 <= packet["timeout_seconds"] <= 1800):
        raise SupervisorError("poll-pair source or bounded target is invalid")
    evidence = packet["evidence_files"]
    if not isinstance(evidence, list) or len(evidence) != 5:
        raise SupervisorError("poll-pair evidence list is incomplete")
    for item in evidence:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"} or
                not isinstance(item["path"], str) or
                not isinstance(item["sha256"], str) or
                not SHA256_RE.fullmatch(item["sha256"])):
            raise SupervisorError("invalid poll-pair evidence pin")
        path = Path(item["path"])
        if (not path.is_absolute() or not path.is_file() or
                not (_inside(path, repo / "tools" / "private") or
                     _inside(path, state)) or
                file_sha256(path) != item["sha256"]):
            raise SupervisorError("poll-pair evidence changed")


def _context(store: JobStore, repo: Path, state: Path,
             baseline_id: str) -> dict:
    context = _baseline(store, repo, state, baseline_id)
    if "execution" in context["packet"]:
        raise SupervisorError("profile-pinned baselines require the strict-update focus lane")
    result = context["result"]
    packet = context["packet"]
    oracle_result = context["sealed"].parent / "oracle" / "oracle-result.json"
    if (result.get("first_divergence") is None or
            result.get("parity_verified") is not False or
            result.get("oracle_result_sha256") != file_sha256(oracle_result) or
            type(packet.get("oracle_target")) is not int or
            packet["oracle_target"] < 120):
        raise SupervisorError("poll-pair baseline is not a sealed mismatch")
    oracle = json.loads(oracle_result.read_text(encoding="utf-8"))
    if (oracle.get("trace_complete") is not True or
            oracle.get("initial_flash_matches_candidate") is not True or
            oracle.get("rom_sha256") != context["job"]["spec"]["pins"]["rom_sha256"]):
        raise SupervisorError("poll-pair baseline oracle provenance changed")
    return context


def queue(store: JobStore, repo: Path, state: Path, baseline_id: str,
          *, target: int = 1500, timeout: int = 600) -> str:
    context = _context(store, repo, state, baseline_id)
    baseline = context["packet"]
    if (type(target) is not int or target > min(
            baseline["native_target"], baseline["oracle_target"])):
        raise SupervisorError("poll-pair target exceeds sealed baseline")
    tool = tool_sha256(repo)
    job_id = job_id_for(baseline_id, target, tool,
                        context["job"]["spec"]["pins"]["native_sha256"])
    source = Path(baseline["source_export"])
    files = [context["sealed"], *(source / name for name in INPUT_NAMES)]
    packet = {"schema": 1, "job_id": job_id, "baseline_id": baseline_id,
              "source_commit": baseline["source_commit"],
              "pin_files": baseline["pin_files"],
              "source_export": baseline["source_export"],
              "target": target, "timeout_seconds": timeout,
              "evidence_files": [
                  {"path": str(path), "sha256": file_sha256(path)} for path in files]}
    validate(packet, repo, state)
    encoded = canonical_bytes(packet)
    directory = state / "poll-pair-packets"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (job_id + ".json")
    if path.exists() and path.read_bytes() != encoded:
        raise SupervisorError("poll-pair job ID already names another packet")
    if not path.exists():
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
    store.enqueue(JobSpec(job_id, pins(packet, repo),
                          ("poll-pair-packet:" + hashlib.sha256(encoded).hexdigest(),),
                          (baseline_id,), "emulator:bizhawk", 1, "json_complete"))
    return job_id


def _controller_context(store: JobStore, repo: Path, state: Path,
                        controller_return_id: str) -> dict:
    from scripts.autonomy.controller_return_job import sealed_context
    context = sealed_context(store, repo, state, controller_return_id)
    packet = context["packet"]
    report = context["report"]
    if (report.get("shared_polls", 0) < 1 or
            report.get("alignment_validated") is not False or
            report.get("parity_verified") is not False):
        raise SupervisorError("controller-return predecessor is incomplete")
    return context


def queue_from_controller_return(store: JobStore, repo: Path, state: Path,
                                 controller_return_id: str, *,
                                 target: int = 1500, timeout: int = 600) -> str:
    context = _controller_context(store, repo, state, controller_return_id)
    predecessor = context["packet"]
    if (type(target) is not int or not 120 <= target <= predecessor["target"]):
        raise SupervisorError("runtime poll-pair target exceeds predecessor")
    source = Path(predecessor["source_export"])
    files = [context["sealed"], *(source / name for name in INPUT_NAMES)]
    job_id = job_id_for(controller_return_id, target, tool_sha256(repo),
                        context["job"]["spec"]["pins"]["native_sha256"])
    packet = {
        "schema": 1, "job_id": job_id,
        "controller_return_id": controller_return_id,
        "source_commit": predecessor["source_commit"],
        "pin_files": predecessor["pin_files"],
        "source_export": predecessor["source_export"],
        "target": target, "timeout_seconds": timeout,
        "evidence_files": [
            {"path": str(path), "sha256": file_sha256(path)}
            for path in files],
    }
    validate(packet, repo, state)
    encoded = canonical_bytes(packet)
    directory = state / "poll-pair-packets"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (job_id + ".json")
    if path.exists() and path.read_bytes() != encoded:
        raise SupervisorError("runtime poll-pair ID names another packet")
    if not path.exists():
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
    store.enqueue(JobSpec(job_id, pins(packet, repo),
                          ("poll-pair-packet:" +
                           hashlib.sha256(encoded).hexdigest(),),
                          (controller_return_id,), "emulator:bizhawk", 1,
                          "json_complete"))
    return job_id


def _complete_pair(attempt_dir: Path, packet: dict, lease: dict) -> dict | None:
    output = attempt_dir / "pair"
    if not all((output / relative).is_file() for relative in (
            "plan.json", "pair-result.json", "comparison.json",
            "native/native-result.json", "oracle/oracle-result.json")):
        return None
    summary = pair.run(output, Path(packet["source_export"]),
                       Path(packet["pin_files"]["native"]),
                       Path(packet["pin_files"]["emulator"]),
                       Path(packet["pin_files"]["rom"]),
                       lease["spec"]["pins"]["rom_sha256"],
                       target=packet["target"], timeout=packet["timeout_seconds"])
    comparison = json.loads((output / "comparison.json").read_text(encoding="utf-8"))
    if (summary.get("complete") is not True or
            summary.get("parity_verified") is not False or
            comparison.get("producer_provenance", {}).get("verified") is not True or
            comparison.get("input_prefix_match") is not True or
            comparison.get("state_scan_complete") is not True):
        raise SupervisorError("poll-pair diagnostic is not complete")
    return {"pair_result_sha256": file_sha256(output / "pair-result.json"),
            "comparison_sha256": file_sha256(output / "comparison.json"),
            "shared_polls": summary["shared_polls"],
            "first_semantic_mismatch": summary["first_semantic_mismatch"]}


def run_lease(store: JobStore, lease: dict, repo: Path, state: Path) -> str:
    job_id, token, attempt = lease["job_id"], lease["token"], lease["attempt"]
    attempt_dir = state / "attempts" / job_id / f"{attempt:04d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    result_path = attempt_dir / "result.json"
    try:
        path = state / "poll-pair-packets" / (job_id + ".json")
        packet = json.loads(path.read_text(encoding="utf-8"))
        validate(packet, repo, state)
        packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        predecessor_id = packet.get("baseline_id") or packet["controller_return_id"]
        if (lease["spec"]["inputs"] != ["poll-pair-packet:" + packet_sha] or
                lease["spec"]["prerequisites"] != [predecessor_id] or
                pins(packet, repo) != lease["spec"]["pins"]):
            raise SupervisorError("poll-pair packet or tool pins changed")
        context = (_context(store, repo, state, predecessor_id)
                   if "baseline_id" in packet else
                   _controller_context(store, repo, state, predecessor_id))
        source = Path(packet["source_export"])
        expected = [context["sealed"], *(source / name for name in INPUT_NAMES)]
        limit = (min(context["packet"]["native_target"],
                     context["packet"]["oracle_target"])
                 if "baseline_id" in packet else context["packet"]["target"])
        if (packet["source_commit"] != context["packet"]["source_commit"] or
                packet["pin_files"] != context["packet"]["pin_files"] or
                packet["source_export"] != context["packet"]["source_export"] or
                packet["target"] > limit or
                packet["evidence_files"] != [
                    {"path": str(item), "sha256": file_sha256(item)}
                    for item in expected]):
            raise SupervisorError("poll-pair baseline evidence changed")
        for previous in store.attempt_history(job_id):
            if previous["number"] >= attempt or previous["outcome"] != "expired":
                continue
            prior = state / "attempts" / job_id / f"{previous['number']:04d}"
            if not expired_attempt_contained(prior):
                raise SupervisorError("expired poll-pair worker may still be live")
            recovered = _complete_pair(prior, packet, lease)
            if recovered is not None:
                _write_json_atomic(result_path, {
                    "schema": 1, "complete": True, "kind": "poll-pair-execution",
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
                return f"{job_id}: prior poll pair recovered"
        store.start(job_id, token)
        command = [real_python_executable(), "-m", "scripts.phase9_poll_semantic_pair",
                   str(attempt_dir / "pair"), "--source", packet["source_export"],
                   "--executable", packet["pin_files"]["native"],
                   "--emulator", packet["pin_files"]["emulator"],
                   "--rom", packet["pin_files"]["rom"],
                   "--rom-sha256", lease["spec"]["pins"]["rom_sha256"],
                   "--target", str(packet["target"]),
                   "--timeout", str(packet["timeout_seconds"])]
        code, reason = bounded_command(
            command, repo, attempt_dir / "pair.stdout", attempt_dir / "pair.stderr",
            time.monotonic() + 2 * packet["timeout_seconds"] + 60,
            lambda: store.heartbeat(job_id, token, ttl=120), state / "PAUSED",
            guard_record=attempt_dir / "pair.guard.json",
            cpu_seconds=2 * packet["timeout_seconds"] + 60)
        if code != 0 or reason is not None:
            raise RuntimeError(f"bounded poll-pair worker failed: {reason or code}")
        complete = _complete_pair(attempt_dir, packet, lease)
        if complete is None:
            raise SupervisorError("poll-pair worker produced no complete bundle")
        validate(packet, repo, state)
        if "controller_return_id" in packet:
            _controller_context(store, repo, state,
                                packet["controller_return_id"])
        if pins(packet, repo) != lease["spec"]["pins"]:
            raise SupervisorError("poll-pair pins changed during capture")
        _write_json_atomic(result_path, {
            "schema": 1, "complete": True, "kind": "poll-pair-execution",
            "job_id": job_id, "attempt": attempt,
            "pair_root": str(attempt_dir / "pair"),
            "packet_sha256": packet_sha, "pins": lease["spec"]["pins"],
            "alignment_validated": False, "parity_verified": False,
            **complete})
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, result_path)
        store.pass_job(job_id, token)
        return f"{job_id}: poll pair sealed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        _write_json_atomic(result_path, {
            "schema": 1, "complete": False, "kind": "poll-pair-execution",
            "job_id": job_id, "attempt": attempt, "stop_reason": str(error)[:300]})
        try:
            store.fail_job(job_id, token, str(error)[:300],
                           blocked=isinstance(error, SupervisorError))
        except JobStoreError:
            pass
        return f"{job_id}: poll pair blocked ({error})"
