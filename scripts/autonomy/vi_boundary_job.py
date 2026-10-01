"""Durable, replay-free VI-boundary analysis of a sealed focused update job."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from scripts.autonomy.job_store import JobSpec, JobStore, JobStoreError, ID_RE
from scripts.autonomy.supervisor import (
    SupervisorError, _git_ok, _inside, _write_json_atomic,
    canonical_bytes, file_sha256,
)
from scripts.compare_phase9_vi_boundary import compare
from scripts.compare_phase9_rdram_transition import compare as compare_transition


TOOL_FILES = (
    "scripts/autonomy/vi_boundary_job.py",
    "scripts/compare_phase9_vi_boundary.py",
    "scripts/compare_phase9_rdram_transition.py",
    "scripts/compare_phase9_focus_rdram.py",
    "scripts/compare_phase9_update_hashes.py",
    "scripts/compare_phase9_retrace_hashes.py",
    "scripts/build_phase9_route_replays.py",
)


def tool_sha256(repo: Path) -> str:
    digest = hashlib.sha256()
    for relative in TOOL_FILES:
        digest.update(relative.encode("ascii"))
        digest.update(bytes.fromhex(file_sha256(repo / relative)))
    return digest.hexdigest()


def _source(packet: dict[str, Any], state: Path) -> tuple[Path, dict, dict]:
    job_id = packet["focus_job_id"]
    sealed = Path(packet["focus_result_path"])
    if (not sealed.is_absolute() or not sealed.is_file() or
            not _inside(sealed, state / "attempts" / job_id) or
            sealed.name != "result.json" or
            file_sha256(sealed) != packet["focus_result_sha256"]):
        raise SupervisorError("VI-boundary predecessor seal is invalid")
    source = json.loads(sealed.read_text(encoding="utf-8"))
    if (source.get("complete") is not True or
            source.get("kind") != "update-execution" or
            source.get("job_id") != job_id or
            source.get("parity_verified") is not False or
            source.get("focus_comparison_sha256") is None or
            source.get("oracle_vi_trace_sha256") is None):
        raise SupervisorError("VI-boundary predecessor is not a focused VI capture")
    focus_packet = state / "update-packets" / (job_id + ".json")
    if (not focus_packet.is_file() or
            file_sha256(focus_packet) != packet["focus_packet_sha256"]):
        raise SupervisorError("VI-boundary focus packet changed")
    parent = json.loads(focus_packet.read_text(encoding="utf-8"))
    if (parent.get("focus_pair") != packet["focus_pair"] or
            source.get("packet_sha256") !=
                hashlib.sha256(canonical_bytes(parent)).hexdigest()):
        raise SupervisorError("VI-boundary focus pair or packet is inconsistent")
    required = {
        "focus-comparison.json": "focus_comparison_sha256",
        "native/retrace-hashes.jsonl.updates.jsonl": "native_trace_sha256",
        "oracle/consumed-vi-hashes.jsonl": "oracle_vi_trace_sha256",
        "oracle/update-hashes.jsonl": "oracle_trace_sha256",
    }
    for relative, field in required.items():
        path = sealed.parent / relative
        if not path.is_file() or (field is not None and
                                  file_sha256(path) != source.get(field)):
            raise SupervisorError(f"VI-boundary source changed: {relative}")
    if file_sha256(sealed.parent / "native" / "retrace-hashes.jsonl") != \
            packet["native_vi_trace_sha256"]:
        raise SupervisorError("VI-boundary native VI trace changed")
    snapshots = source.get("focus_snapshot_sha256")
    if not isinstance(snapshots, dict) or not snapshots:
        raise SupervisorError("VI-boundary source lacks sealed snapshots")
    for relative, digest in snapshots.items():
        name = Path(relative)
        if (name.is_absolute() or len(name.parts) != 2 or
                name.parts[0] not in ("native", "oracle") or
                not name.parts[1].startswith("focus-update-") or
                name.suffix != ".rdram" or
                file_sha256(sealed.parent / name) != digest):
            raise SupervisorError("VI-boundary snapshot seal changed")
    return sealed, source, parent


def validate(packet: dict[str, Any], repo: Path, state: Path) -> None:
    required = {"schema", "job_id", "source_commit", "focus_job_id",
                "focus_result_path", "focus_result_sha256",
                "focus_packet_sha256", "focus_pair", "native_vi_trace_sha256"}
    if (not isinstance(packet, dict) or set(packet) != required or
            packet["schema"] != 1 or
            any(not isinstance(packet[key], str) or not ID_RE.fullmatch(packet[key])
                for key in ("job_id", "focus_job_id")) or
            not isinstance(packet["source_commit"], str) or
            _git_ok(repo, "rev-parse", "--verify",
                    packet["source_commit"] + "^{commit}") != packet["source_commit"] or
            any(not isinstance(packet[key], str) or len(packet[key]) != 64
                for key in ("focus_result_sha256", "focus_packet_sha256",
                            "native_vi_trace_sha256"))):
        raise SupervisorError("invalid VI-boundary packet")
    _source(packet, state)


def queue_boundary(store: JobStore, repo: Path, state: Path, *,
                   job_id: str, focus_job_id: str) -> None:
    parent_job = store.job(focus_job_id)
    if (parent_job["state"] != "passed" or
            not parent_job["sealed_artifact"] or
            not parent_job["sealed_sha256"]):
        raise SupervisorError("VI-boundary predecessor is not passed and sealed")
    focus_packet = state / "update-packets" / (focus_job_id + ".json")
    parent = json.loads(focus_packet.read_text(encoding="utf-8"))
    packet = {
        "schema": 1, "job_id": job_id,
        "source_commit": _git_ok(repo, "rev-parse", "HEAD"),
        "focus_job_id": focus_job_id,
        "focus_result_path": parent_job["sealed_artifact"],
        "focus_result_sha256": parent_job["sealed_sha256"],
        "focus_packet_sha256": file_sha256(focus_packet),
        "native_vi_trace_sha256": file_sha256(
            Path(parent_job["sealed_artifact"]).parent / "native" /
            "retrace-hashes.jsonl"),
        "focus_pair": parent["focus_pair"],
    }
    validate(packet, repo, state)
    pins = dict(parent_job["spec"]["pins"])
    pins["source_commit"] = packet["source_commit"]
    pins["tool_sha256"] = tool_sha256(repo)
    encoded = canonical_bytes(packet)
    digest = hashlib.sha256(encoded).hexdigest()
    packet_dir = state / "vi-boundary-packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    target = packet_dir / (job_id + ".json")
    if target.exists() and target.read_bytes() != encoded:
        raise SupervisorError("VI-boundary ID names a different packet")
    if not target.exists():
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(target)
    store.enqueue(JobSpec(job_id, pins, ("vi-boundary-packet:" + digest,),
                          (focus_job_id,), "analysis:vi-boundary", 1,
                          "json_complete"))


def run_boundary_lease(store: JobStore, lease: dict[str, Any],
                       repo: Path, state: Path) -> str:
    job_id, token, attempt = lease["job_id"], lease["token"], lease["attempt"]
    directory = state / "attempts" / job_id / f"{attempt:04d}"
    directory.mkdir(parents=True, exist_ok=True)
    result_path = directory / "result.json"
    try:
        packet = json.loads((state / "vi-boundary-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        validate(packet, repo, state)
        digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (lease["spec"]["inputs"] != ["vi-boundary-packet:" + digest] or
                lease["spec"]["prerequisites"] != [packet["focus_job_id"]] or
                lease["spec"]["pins"]["source_commit"] != packet["source_commit"] or
                lease["spec"]["pins"]["tool_sha256"] != tool_sha256(repo)):
            raise SupervisorError("VI-boundary packet or tools changed")
        parent_job = store.job(packet["focus_job_id"])
        if (parent_job["state"] != "passed" or
                parent_job["sealed_sha256"] != packet["focus_result_sha256"] or
                any(parent_job["spec"]["pins"][key] !=
                    lease["spec"]["pins"][key] for key in
                    ("rom_sha256", "emulator_sha256", "native_sha256"))):
            raise SupervisorError("VI-boundary predecessor pins changed")
        for previous in store.attempt_history(job_id):
            if previous["number"] >= attempt or previous["outcome"] != "expired":
                continue
            prior = state / "attempts" / job_id / f"{previous['number']:04d}"
            prior_result = prior / "result.json"
            prior_report = prior / "vi-boundary-comparison.json"
            prior_transition = prior / "rdram-transition-comparison.json"
            if (prior_result.is_file() and prior_report.is_file() and
                    prior_transition.is_file()):
                old = json.loads(prior_result.read_text(encoding="utf-8"))
                prior_comparison = json.loads(prior_report.read_text(encoding="utf-8"))
                old_transition = json.loads(prior_transition.read_text(encoding="utf-8"))
                if (old.get("complete") is True and
                        old.get("kind") == "vi-boundary-execution" and
                        old.get("job_id") == job_id and
                        old.get("packet_sha256") == digest and
                        old.get("pins") == lease["spec"]["pins"] and
                        old.get("comparison_sha256") == file_sha256(prior_report) and
                        old.get("rdram_transition_sha256") ==
                            file_sha256(prior_transition) and
                        old.get("parity_verified") is False and
                        prior_comparison.get("kind") ==
                            "jfg-phase9-vi-boundary-comparison" and
                        prior_comparison.get("parity_verified") is False and
                        old_transition.get("kind") ==
                            "jfg-phase9-rdram-transition-comparison" and
                        old_transition.get("parity_verified") is False):
                    store.start(job_id, token)
                    store.verify(job_id, token)
                    store.seal_artifact(job_id, token, prior_result)
                    store.pass_job(job_id, token)
                    return f"{job_id}: prior VI-boundary report recovered"
        store.start(job_id, token)
        sealed, _, _ = _source(packet, state)
        report = compare(sealed.parent / "native", sealed.parent / "oracle",
                         **packet["focus_pair"])
        report_path = directory / "vi-boundary-comparison.json"
        _write_json_atomic(report_path, report)
        transition = compare_transition(
            sealed.parent / "native", sealed.parent / "oracle",
            **packet["focus_pair"])
        transition_path = directory / "rdram-transition-comparison.json"
        _write_json_atomic(transition_path, transition)
        validate(packet, repo, state)
        if tool_sha256(repo) != lease["spec"]["pins"]["tool_sha256"]:
            raise SupervisorError("VI-boundary tools changed during analysis")
        _write_json_atomic(result_path, {
            "schema": 1, "complete": True, "kind": "vi-boundary-execution",
            "job_id": job_id, "attempt": attempt,
            "packet_sha256": digest, "pins": lease["spec"]["pins"],
            "focus_result_sha256": packet["focus_result_sha256"],
            "comparison_sha256": file_sha256(report_path),
            "rdram_transition_sha256": file_sha256(transition_path),
            "alignment_validated": False, "parity_verified": False,
        })
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, result_path)
        store.pass_job(job_id, token)
        return f"{job_id}: VI-boundary report sealed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        _write_json_atomic(result_path, {
            "schema": 1, "complete": False, "kind": "vi-boundary-execution",
            "job_id": job_id, "attempt": attempt, "stop_reason": str(error)[:300],
        })
        try:
            store.fail_job(job_id, token, str(error)[:300],
                           blocked=isinstance(error, SupervisorError))
        except JobStoreError:
            pass
        return f"{job_id}: VI-boundary analysis blocked ({error})"
