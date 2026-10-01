"""Ledger successor that analyzes sealed poll-pair cadence without a model."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.autonomy.job_store import ID_RE, SHA256_RE, JobSpec, JobStore, JobStoreError
from scripts.autonomy.supervisor import (
    SupervisorError, _git_ok, _inside, _write_json_atomic, canonical_bytes,
    file_sha256,
)
from scripts.phase9_poll_lag_analysis import analyze
from scripts.phase9_poll_call_phase import (
    FIELDS as CALL_PHASE_FIELDS, analyze as analyze_call_phase,
)


TOOL_FILES = (
    "scripts/autonomy/atomic_file.py",
    "scripts/autonomy/poll_lag_job.py",
    "scripts/autonomy/supervisor.py",
    "scripts/autonomy/job_store.py",
    "scripts/phase9_poll_lag_analysis.py",
    "scripts/phase9_poll_call_phase.py",
    "scripts/compare_phase9_poll_hashes.py",
    "scripts/compare_phase9_retrace_hashes.py",
    "scripts/build_phase9_route_replays.py",
    "scripts/phase95_bridge.py",
)
PAIR_NAMES = (
    "plan.json", "pair-result.json", "comparison.json",
    "native/retrace-hashes.jsonl.polls.jsonl", "oracle/poll-hashes.jsonl",
    "native/native-result.json", "oracle/oracle-result.json",
)
SOURCE_NAMES = ("export-manifest.json", "controller.input",
                "initial.flash", "initial.pak")


def call_phase_available(native: Path, oracle: Path) -> bool:
    """Only old traces may omit both counter pairs; mixed traces are invalid."""
    available = []
    for path in (native, oracle):
        with path.open(encoding="utf-8") as stream:
            next(stream, None)  # The lag analyzer validates the full trace.
            observed = None
            for line in stream:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise SupervisorError("poll trace has a non-object state row")
                present = [field in row for field in CALL_PHASE_FIELDS]
                if any(present) and not all(present):
                    raise SupervisorError("poll trace has partial call-phase counters")
                if observed is not None and observed != all(present):
                    raise SupervisorError("poll trace mixes call-phase schemas")
                observed = all(present)
        if observed is None:
            raise SupervisorError("poll trace has no state rows")
        available.append(observed)
    if available[0] != available[1]:
        raise SupervisorError("native/oracle call-phase provenance is mixed")
    return available[0]


def tool_sha256(repo: Path) -> str:
    digest = hashlib.sha256()
    for relative in TOOL_FILES:
        digest.update(relative.encode("ascii"))
        digest.update(bytes.fromhex(file_sha256(repo / relative)))
    return digest.hexdigest()


def job_id_for(pair_job_id: str, radius: int, tool_sha: str) -> str:
    digest = hashlib.sha256(canonical_bytes({
        "pair_job_id": pair_job_id, "radius": radius,
        "tool_sha256": tool_sha,
    })).hexdigest()[:24]
    return "poll-lag-" + digest


def _context(store: JobStore, state: Path, pair_job_id: str) -> dict:
    job = store.job(pair_job_id)
    if (job["state"] != "passed" or not job["spec"]["inputs"] or
            not job["spec"]["inputs"][0].startswith("poll-pair-packet:") or
            not job["sealed_artifact"] or not job["sealed_sha256"]):
        raise SupervisorError("lag predecessor is not a sealed poll pair")
    sealed = Path(job["sealed_artifact"]).resolve(strict=True)
    if (not sealed.is_relative_to((state / "attempts" / pair_job_id).resolve()) or
            sealed.name != "result.json" or
            file_sha256(sealed) != job["sealed_sha256"]):
        raise SupervisorError("poll-pair predecessor seal changed")
    result = json.loads(sealed.read_text(encoding="utf-8"))
    packet = json.loads((state / "poll-pair-packets" /
                         (pair_job_id + ".json")).read_text(encoding="utf-8"))
    packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    if (result.get("complete") is not True or
            result.get("kind") != "poll-pair-execution" or
            result.get("job_id") != pair_job_id or
            result.get("packet_sha256") != packet_sha or
            result.get("pins") != job["spec"]["pins"] or
            result.get("alignment_validated") is not False or
            result.get("parity_verified") is not False or
            job["spec"]["inputs"] != ["poll-pair-packet:" + packet_sha] or
            packet.get("source_commit") != job["spec"]["pins"]["source_commit"]):
        raise SupervisorError("poll-pair predecessor provenance changed")
    pair_root = Path(result.get("pair_root", "")).resolve(strict=True)
    if (pair_root.name != "pair" or
            not pair_root.is_relative_to(
                (state / "attempts" / pair_job_id).resolve())):
        raise SupervisorError("poll-pair output leaves its attempt tree")
    source = Path(packet["source_export"]).resolve(strict=True)
    if not _inside(source, state.parent):
        raise SupervisorError("poll-pair selected input is not private")
    plan = json.loads((pair_root / "plan.json").read_text(encoding="utf-8"))
    pair_result = json.loads((pair_root / "pair-result.json").read_text(
        encoding="utf-8"))
    if (plan.get("source_export") != str(source) or
            plan.get("target") != packet.get("target") or
            pair_result.get("complete") is not True or
            pair_result.get("comparison_sha256") != file_sha256(
                pair_root / "comparison.json") or
            pair_result.get("native_result_sha256") != file_sha256(
                pair_root / "native" / "native-result.json") or
            pair_result.get("oracle_result_sha256") != file_sha256(
                pair_root / "oracle" / "oracle-result.json") or
            result.get("pair_result_sha256") != file_sha256(
                pair_root / "pair-result.json") or
            result.get("comparison_sha256") != file_sha256(
                pair_root / "comparison.json")):
        raise SupervisorError("poll-pair producer result or plan changed")
    files = [sealed, *(pair_root / name for name in PAIR_NAMES),
             *(source / name for name in SOURCE_NAMES)]
    return {"job": job, "result": result, "packet": packet,
            "source": source, "pair_root": pair_root, "files": files}


def _pins(context: dict, repo: Path) -> dict[str, str]:
    return {**context["job"]["spec"]["pins"],
            "tool_sha256": tool_sha256(repo)}


def validate(packet: dict, repo: Path, state: Path) -> None:
    expected = {"schema", "job_id", "pair_job_id", "source_commit",
                "source_export", "pair_root", "radius", "evidence_files"}
    if (not isinstance(packet, dict) or set(packet) != expected or
            packet["schema"] != 1 or
            any(not isinstance(packet[key], str) or not ID_RE.fullmatch(packet[key])
                for key in ("job_id", "pair_job_id")) or
            type(packet["radius"]) is not int or not 1 <= packet["radius"] <= 32):
        raise SupervisorError("invalid poll-lag packet")
    if (not isinstance(packet["source_commit"], str) or
            _git_ok(repo, "rev-parse", "--verify",
                    packet["source_commit"] + "^{commit}") !=
            packet["source_commit"]):
        raise SupervisorError("poll-lag source commit is not pinned")
    source = Path(packet["source_export"])
    pair_root = Path(packet["pair_root"])
    if (not source.is_absolute() or not source.is_dir() or
            not _inside(source, repo / "tools" / "private") or
            not pair_root.is_absolute() or not pair_root.is_dir() or
            not _inside(pair_root, state / "attempts" / packet["pair_job_id"])):
        raise SupervisorError("poll-lag input roots are not private")
    evidence = packet["evidence_files"]
    if not isinstance(evidence, list) or len(evidence) != 12:
        raise SupervisorError("poll-lag evidence list is incomplete")
    for item in evidence:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"} or
                not isinstance(item["path"], str) or
                not isinstance(item["sha256"], str) or
                not SHA256_RE.fullmatch(item["sha256"])):
            raise SupervisorError("invalid poll-lag evidence pin")
        path = Path(item["path"])
        if (not path.is_absolute() or not path.is_file() or
                not _inside(path, repo / "tools" / "private") or
                file_sha256(path) != item["sha256"]):
            raise SupervisorError("poll-lag evidence changed")


def queue(store: JobStore, repo: Path, state: Path, pair_job_id: str,
          *, radius: int = 8) -> str:
    context = _context(store, state, pair_job_id)
    if type(radius) is not int or not 1 <= radius <= 32:
        raise SupervisorError("poll-lag radius must be 1..32")
    job_id = job_id_for(pair_job_id, radius, tool_sha256(repo))
    packet = {"schema": 1, "job_id": job_id, "pair_job_id": pair_job_id,
              "source_commit": context["packet"]["source_commit"],
              "source_export": str(context["source"]),
              "pair_root": str(context["pair_root"]), "radius": radius,
              "evidence_files": [
                  {"path": str(path), "sha256": file_sha256(path)}
                  for path in context["files"]]}
    validate(packet, repo, state)
    encoded = canonical_bytes(packet)
    directory = state / "poll-lag-packets"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (job_id + ".json")
    if path.exists() and path.read_bytes() != encoded:
        raise SupervisorError("poll-lag job ID already names another packet")
    if not path.exists():
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
    store.enqueue(JobSpec(
        job_id, _pins(context, repo),
        ("poll-lag-packet:" + hashlib.sha256(encoded).hexdigest(),),
        (pair_job_id,), "analysis:poll-lag", 1, "json_complete"))
    return job_id


def run_lease(store: JobStore, lease: dict, repo: Path, state: Path) -> str:
    job_id, token, attempt = lease["job_id"], lease["token"], lease["attempt"]
    attempt_dir = state / "attempts" / job_id / f"{attempt:04d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    result_path = attempt_dir / "result.json"
    try:
        packet = json.loads((state / "poll-lag-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        validate(packet, repo, state)
        context = _context(store, state, packet["pair_job_id"])
        expected = [{"path": str(path), "sha256": file_sha256(path)}
                    for path in context["files"]]
        packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (packet["source_export"] != str(context["source"]) or
                packet["pair_root"] != str(context["pair_root"]) or
                packet["source_commit"] !=
                    context["packet"]["source_commit"] or
                packet["evidence_files"] != expected or
                lease["spec"]["inputs"] != ["poll-lag-packet:" + packet_sha] or
                lease["spec"]["prerequisites"] != [packet["pair_job_id"]] or
                lease["spec"]["pins"] != _pins(context, repo)):
            raise SupervisorError("poll-lag packet or tool pins changed")
        store.start(job_id, token)
        pair_root = context["pair_root"]
        try:
            report = analyze(
                context["source"],
                pair_root / "native" / "retrace-hashes.jsonl.polls.jsonl",
                pair_root / "oracle" / "poll-hashes.jsonl",
                pair_root / "comparison.json", radius=packet["radius"])
        except ValueError as error:
            raise SupervisorError(f"poll-lag analysis rejected evidence: {error}") from error
        report_path = attempt_dir / "lag-report.json"
        _write_json_atomic(report_path, report)
        native_trace = pair_root / "native" / "retrace-hashes.jsonl.polls.jsonl"
        oracle_trace = pair_root / "oracle" / "poll-hashes.jsonl"
        phase_report = None
        phase_path = attempt_dir / "call-phase-report.json"
        if call_phase_available(native_trace, oracle_trace):
            try:
                phase_report = analyze_call_phase(
                    native_trace, oracle_trace,
                    prefix_polls=report["compared_polls"])
            except (KeyError, ValueError) as error:
                raise SupervisorError(
                    f"call-phase analysis rejected evidence: {error}") from error
            _write_json_atomic(phase_path, phase_report)
        validate(packet, repo, state)
        if _pins(context, repo) != lease["spec"]["pins"]:
            raise SupervisorError("poll-lag tool pins changed during analysis")
        _write_json_atomic(result_path, {
            "schema": 1, "complete": True, "kind": "poll-lag-execution",
            "job_id": job_id, "attempt": attempt,
            "packet_sha256": packet_sha, "pins": lease["spec"]["pins"],
            "lag_report_sha256": file_sha256(report_path),
            "call_phase_report_sha256": file_sha256(phase_path)
            if phase_report is not None else None,
            "same_call_phase": phase_report["same_call_phase"]
            if phase_report is not None else None,
            "call_phase_hooks_observed": phase_report["hooks_observed"]
            if phase_report is not None else None,
            "mismatching_polls": report["mismatching_polls"],
            "unique_shift_match": report["unique_shift_match"],
            "ambiguous_shift_match": report["ambiguous_shift_match"],
            "no_shift_match": report["no_shift_match"],
            "alignment_validated": False, "parity_verified": False,
        })
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, result_path)
        store.pass_job(job_id, token)
        return f"{job_id}: poll-lag report sealed"
    except (OSError, ValueError, RuntimeError) as error:
        _write_json_atomic(result_path, {
            "schema": 1, "complete": False, "kind": "poll-lag-execution",
            "job_id": job_id, "attempt": attempt,
            "stop_reason": str(error)[:300],
        })
        try:
            store.fail_job(job_id, token, str(error)[:300],
                           blocked=isinstance(error, SupervisorError))
        except JobStoreError:
            pass
        return f"{job_id}: poll-lag blocked ({error})"
