"""Pinned, restartable BizHawk poll/VI alignment diagnostic job."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Any

from scripts.autonomy.job_store import JobSpec, JobStore, JobStoreError, ID_RE, SHA256_RE
from scripts.autonomy.process_guard import real_python_executable
from scripts.autonomy.supervisor import (
    PIN_FILES, SupervisorError, _git_ok, _inside, _write_json_atomic,
    bounded_command, canonical_bytes, expired_attempt_contained, file_sha256,
)


TOOL_FILES = (
    "scripts/autonomy/alignment_job.py",
    "scripts/phase95_oracle_replay.py",
    "scripts/phase9_oracle_instruction_effects.py",
    "scripts/phase9_point_probe.py",
    "scripts/phase9_bizhawk_oracle.lua",
    "scripts/phase9_poll_vi_alignment.py",
    "scripts/phase95_poll_compare.py",
    "scripts/phase95_bridge.py",
    "scripts/compare_phase9_retrace_hashes.py",
)


def alignment_tool_sha256(repo: Path) -> str:
    digest = hashlib.sha256()
    for relative in TOOL_FILES:
        digest.update(relative.encode("ascii"))
        digest.update(bytes.fromhex(file_sha256(repo / relative)))
    return digest.hexdigest()


def evidence(path: Path) -> dict[str, str]:
    path = path.resolve(strict=True)
    return {"path": str(path), "sha256": file_sha256(path)}


def validate_alignment_packet(packet: dict[str, Any], repo: Path) -> None:
    required = {"schema", "job_id", "source_commit", "pin_files",
                "source_export", "native_replay", "diagnosis_id",
                "evidence_files", "target_frame", "max_polls", "timeout_seconds"}
    if not isinstance(packet, dict) or set(packet) != required or packet["schema"] != 1:
        raise SupervisorError("invalid alignment packet schema")
    if (not isinstance(packet["job_id"], str) or
            not ID_RE.fullmatch(packet["job_id"]) or
            not isinstance(packet["diagnosis_id"], str) or
            not ID_RE.fullmatch(packet["diagnosis_id"])):
        raise SupervisorError("invalid alignment or diagnosis ID")
    if not isinstance(packet["source_commit"], str) or len(packet["source_commit"]) not in (40, 64):
        raise SupervisorError("alignment source commit is not a full local commit")
    if _git_ok(repo, "rev-parse", "--verify", packet["source_commit"] + "^{commit}") != \
            packet["source_commit"]:
        raise SupervisorError("alignment source commit is not a full local commit")
    if (type(packet["target_frame"]) is not int or
            not 3 <= packet["target_frame"] <= 600 or
            type(packet["max_polls"]) is not int or
            not 1 <= packet["max_polls"] <= 1000 or
            type(packet["timeout_seconds"]) is not int or
            not 30 <= packet["timeout_seconds"] <= 900):
        raise SupervisorError("alignment capture limits are invalid")
    if not isinstance(packet["pin_files"], dict) or set(packet["pin_files"]) != set(PIN_FILES):
        raise SupervisorError("alignment ROM/emulator/native pins are incomplete")
    for key in PIN_FILES:
        if not isinstance(packet["pin_files"][key], str):
            raise SupervisorError("alignment binary pin is invalid")
        path = Path(packet["pin_files"][key])
        if not path.is_absolute() or not path.is_file():
            raise SupervisorError("alignment binary pin is missing")
    for key in ("source_export", "native_replay"):
        if not isinstance(packet[key], str):
            raise SupervisorError("alignment input directory is invalid")
        path = Path(packet[key])
        if not path.is_absolute() or not path.is_dir() or not _inside(path, repo / "tools" / "private"):
            raise SupervisorError("alignment input directory must be private")
    files = packet["evidence_files"]
    if not isinstance(files, list) or not 1 <= len(files) <= 12:
        raise SupervisorError("alignment evidence list is invalid")
    for item in files:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"} or
                not isinstance(item["path"], str) or
                not isinstance(item["sha256"], str) or
                not SHA256_RE.fullmatch(item["sha256"])):
            raise SupervisorError("alignment evidence pin is invalid")
        path = Path(item["path"])
        if (not path.is_absolute() or not path.is_file() or
                not _inside(path, repo / "tools" / "private") or
                file_sha256(path) != item["sha256"]):
            raise SupervisorError("alignment evidence changed or escaped private storage")


def alignment_pins(packet: dict[str, Any], repo: Path) -> dict[str, str]:
    return {"source_commit": packet["source_commit"],
            "tool_sha256": alignment_tool_sha256(repo),
            **{key + "_sha256": file_sha256(Path(packet["pin_files"][key]))
               for key in PIN_FILES}}


def queue_alignment(store: JobStore, repo: Path, state: Path, *, job_id: str,
                    diagnosis_id: str, diagnosis_path: Path,
                    comparison_packet: dict[str, Any],
                    target_frame: int = 120) -> None:
    """Queue one boot-prefix probe from a diagnosed capture mismatch."""
    native = Path(comparison_packet["native_trace"]["path"]).resolve(strict=True).parent
    oracle = Path(comparison_packet["oracle_trace"]["path"]).resolve(strict=True).parent
    oracle_result = json.loads((oracle / "oracle-result.json").read_text(encoding="utf-8"))
    native_result = json.loads((native / "native-result.json").read_text(encoding="utf-8"))
    source = Path(oracle_result["source_export"]).resolve(strict=True)
    export = json.loads((source / "export-manifest.json").read_text(encoding="utf-8"))
    if (native_result.get("source_export") != str(source) or
            oracle_result.get("source_export_sha256") !=
                file_sha256(source / "export-manifest.json") or
            oracle_result.get("input_sha256") != native_result.get("input_sha256") or
            export.get("input_sha256") != oracle_result.get("input_sha256") or
            type(export.get("oracle_final_frame")) is not int or
            target_frame > export["oracle_final_frame"] or
            oracle_result.get("rom_sha256") !=
                file_sha256(Path(comparison_packet["pin_files"]["rom"]))):
        raise SupervisorError("comparison replays do not share a pinned export")
    paths = [source / name for name in ("export-manifest.json", "controller.input",
                                       "initial.flash", "initial.pak")]
    paths += [native / name for name in ("native-result.json", "controller-polls.tsv",
                                         "retrace-hashes.jsonl")]
    paths += [oracle / "oracle-result.json", diagnosis_path]
    packet = {
        "schema": 1, "job_id": job_id,
        "source_commit": _git_ok(repo, "rev-parse", "HEAD"),
        "pin_files": comparison_packet["pin_files"],
        "source_export": str(source), "native_replay": str(native),
        "diagnosis_id": diagnosis_id,
        "evidence_files": [evidence(path) for path in paths],
        "target_frame": target_frame, "max_polls": 256,
        "timeout_seconds": 600,
    }
    validate_alignment_packet(packet, repo)
    state.mkdir(parents=True, exist_ok=True)
    encoded = canonical_bytes(packet)
    digest = hashlib.sha256(encoded).hexdigest()
    packet_dir = state / "alignment-packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    target = packet_dir / (job_id + ".json")
    if target.exists() and target.read_bytes() != encoded:
        raise SupervisorError("alignment job ID already names a different packet")
    if not target.exists():
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(target)
    store.enqueue(JobSpec(job_id, alignment_pins(packet, repo),
                          ("alignment-packet:" + digest,), (diagnosis_id,),
                          "emulator:bizhawk", 1, "json_complete"))


def _recover(store: JobStore, lease: dict[str, Any], prior: Path) -> bool:
    result_path = prior / "result.json"
    report_path = prior / "alignment.json"
    oracle_path = prior / "oracle" / "oracle-result.json"
    if not result_path.is_file():
        return False
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("complete") is not True:
        return False
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    expected = lease["spec"]["inputs"][0].split(":", 1)[1]
    if (result.get("kind") != "alignment-execution" or
            result.get("job_id") != lease["job_id"] or
            result.get("packet_sha256") != expected or
            result.get("pins") != lease["spec"]["pins"] or
            not oracle_path.is_file() or
            result.get("oracle_result_sha256") != file_sha256(oracle_path) or
            not report_path.is_file() or
            result.get("alignment_sha256") != file_sha256(report_path) or
            report.get("kind") != "jfg-phase9-poll-vi-alignment" or
            report.get("alignment_validated") is not False or
            report.get("first_validated_gameplay_divergence") is not None or
            result.get("parity_verified") is not False):
        raise SupervisorError("expired alignment bundle is inconsistent")
    store.start(lease["job_id"], lease["token"])
    store.verify(lease["job_id"], lease["token"])
    store.seal_artifact(lease["job_id"], lease["token"], result_path)
    store.pass_job(lease["job_id"], lease["token"])
    return True


def run_alignment_lease(store: JobStore, lease: dict[str, Any],
                        repo: Path, state: Path) -> str:
    job_id, token, attempt = lease["job_id"], lease["token"], lease["attempt"]
    attempt_dir = state / "attempts" / job_id / f"{attempt:04d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    result_path = attempt_dir / "result.json"
    try:
        packet = json.loads((state / "alignment-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        validate_alignment_packet(packet, repo)
        digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (lease["spec"]["inputs"] != ["alignment-packet:" + digest] or
                alignment_pins(packet, repo) != lease["spec"]["pins"] or
                lease["spec"]["prerequisites"] != [packet["diagnosis_id"]]):
            raise SupervisorError("alignment packet or tool pins changed")
        for previous in store.attempt_history(job_id):
            if previous["number"] >= attempt or previous["outcome"] != "expired":
                continue
            prior = state / "attempts" / job_id / f"{previous['number']:04d}"
            if list(prior.glob("*.guard.json")) or (prior / "result.json").is_file():
                if not expired_attempt_contained(prior):
                    raise SupervisorError("expired alignment child may still be alive")
                if _recover(store, lease, prior):
                    return f"{job_id}: prior alignment recovered"
        store.start(job_id, token)
        deadline = time.monotonic() + packet["timeout_seconds"]
        heartbeat = lambda: store.heartbeat(job_id, token, ttl=120)
        oracle_output = attempt_dir / "oracle"
        command = [real_python_executable(), "-m", "scripts.phase95_oracle_replay",
                   str(oracle_output), "--emulator", packet["pin_files"]["emulator"],
                   "--rom", packet["pin_files"]["rom"], "--rom-sha256",
                   lease["spec"]["pins"]["rom_sha256"], "--source",
                   packet["source_export"], "--target-frame", str(packet["target_frame"]),
                   "--vi-trace", "--timeout", str(packet["timeout_seconds"] - 30)]
        code, reason = bounded_command(
            command, repo, attempt_dir / "oracle.stdout", attempt_dir / "oracle.stderr",
            deadline, heartbeat, state / "PAUSED",
            guard_record=attempt_dir / "oracle.guard.json")
        if code != 0 or reason:
            raise SupervisorError("bounded oracle alignment capture failed")
        report_path = attempt_dir / "alignment.json"
        analyze = [real_python_executable(), "-m", "scripts.phase9_poll_vi_alignment",
                   packet["source_export"], str(oracle_output), packet["native_replay"],
                   "--max-polls", str(packet["max_polls"]), "--output", str(report_path)]
        code, reason = bounded_command(
            analyze, repo, attempt_dir / "alignment.stdout",
            attempt_dir / "alignment.stderr", deadline, heartbeat,
            state / "PAUSED", guard_record=attempt_dir / "alignment.guard.json")
        if code != 0 or reason or not report_path.is_file():
            raise SupervisorError("bounded poll/VI alignment analysis failed")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (report.get("kind") != "jfg-phase9-poll-vi-alignment" or
                report.get("alignment_validated") is not False or
                report.get("first_validated_gameplay_divergence") is not None):
            raise SupervisorError("alignment report made an unsupported parity claim")
        validate_alignment_packet(packet, repo)
        if alignment_pins(packet, repo) != lease["spec"]["pins"]:
            raise SupervisorError("alignment inputs changed during execution")
        _write_json_atomic(result_path, {
            "schema": 1, "complete": True, "kind": "alignment-execution",
            "job_id": job_id, "attempt": attempt, "packet_sha256": digest,
            "pins": lease["spec"]["pins"],
            "oracle_result_sha256": file_sha256(oracle_output / "oracle-result.json"),
            "alignment_sha256": file_sha256(report_path),
            "shared_polls_analyzed": report["shared_polls_analyzed"],
            "alignment_validated": False, "parity_verified": False,
        })
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, result_path)
        store.pass_job(job_id, token)
        return f"{job_id}: alignment diagnostic sealed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        _write_json_atomic(result_path, {
            "schema": 1, "complete": False, "kind": "alignment-execution",
            "job_id": job_id, "attempt": attempt,
            "stop_reason": str(error)[:300],
        })
        try:
            store.fail_job(job_id, token, str(error)[:300],
                           blocked=isinstance(error, SupervisorError))
        except JobStoreError:
            pass
        return f"{job_id}: alignment blocked ({error})"
