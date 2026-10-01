"""Pinned parallel native-repeat diagnostic for a sealed selected-input route.

Identical native runs establish repeatability of this prefix only. They do not
establish native/oracle alignment, input equivalence, or gameplay parity.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Any

from scripts.autonomy.job_store import ID_RE, JobSpec, JobStore, JobStoreError, SHA256_RE
from scripts.autonomy.process_guard import real_python_executable
from scripts.autonomy.supervisor import (
    PIN_FILES, SupervisorError, _inside, _write_json_atomic, bounded_command,
    canonical_bytes, expired_attempt_contained, file_sha256,
)
from scripts.autonomy.update_job import validate as validate_update_packet
from scripts.autonomy import execution_contract as execution
from scripts.compare_phase9_retrace_hashes import compare as compare_retraces
from scripts.compare_phase9_update_hashes import compare as compare_updates


TOOL_FILES = (
    "scripts/autonomy/atomic_file.py",
    "scripts/autonomy/determinism_job.py",
    "scripts/autonomy/execution_contract.py",
    "scripts/autonomy/source_build.py",
    "scripts/autonomy/source_snapshot.py",
    "scripts/autonomy/update_job.py",
    "scripts/phase95_bridge.py",
    "scripts/autonomy/supervisor.py",
    "scripts/phase95_native_replay.py",
    "scripts/phase9_point_probe.py",
    "scripts/compare_phase9_retrace_hashes.py",
    "scripts/compare_phase9_update_hashes.py",
)
EVIDENCE_NAMES = (
    "export-manifest.json", "controller.input", "initial.flash", "initial.pak",
)


def tool_sha256(repo: Path) -> str:
    digest = hashlib.sha256()
    for relative in TOOL_FILES:
        digest.update(relative.encode("ascii"))
        digest.update(bytes.fromhex(file_sha256(repo / relative)))
    return digest.hexdigest()


def determinism_id(export_sha256: str, native_sha256: str,
                   source_commit: str, target_retraces: int,
                   runs: int, parallelism: int, execution_contract=None) -> str:
    identity = {
        "export_sha256": export_sha256, "runs": runs,
        "parallelism": parallelism, "native_sha256": native_sha256,
        "source_commit": source_commit, "target_retraces": target_retraces,
    }
    if execution_contract is not None:
        identity["execution"] = execution_contract
    key = hashlib.sha256(canonical_bytes(identity)).hexdigest()[:24]
    return "native-det-" + key


def _baseline(store: JobStore, repo: Path, state: Path,
              baseline_id: str) -> dict[str, Any]:
    job = store.job(baseline_id)
    if (job["state"] != "passed" or not job["spec"]["inputs"] or
            not job["spec"]["inputs"][0].startswith("update-packet:") or
            not job["sealed_artifact"] or not job["sealed_sha256"]):
        raise SupervisorError("determinism baseline is not a sealed update job")
    sealed = Path(job["sealed_artifact"]).resolve(strict=True)
    if (not sealed.is_relative_to((state / "attempts" / baseline_id).resolve()) or
            sealed.name != "result.json" or
            file_sha256(sealed) != job["sealed_sha256"]):
        raise SupervisorError("determinism baseline seal changed")
    packet_path = state / "update-packets" / (baseline_id + ".json")
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    validate_update_packet(packet, repo)
    execution.require_current(packet)
    digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    result = json.loads(sealed.read_text(encoding="utf-8"))
    if (job["spec"]["inputs"] != ["update-packet:" + digest] or
            job["spec"]["pins"]["source_commit"] != packet["source_commit"] or
            any(job["spec"]["pins"][key + "_sha256"] !=
                file_sha256(Path(packet["pin_files"][key])) for key in PIN_FILES) or
            result.get("complete") is not True or
            result.get("kind") != "update-execution" or
            result.get("job_id") != baseline_id or
            result.get("packet_sha256") != digest or
            result.get("pins") != job["spec"]["pins"] or
            result.get("input_prefix_match") is not True):
        raise SupervisorError("determinism baseline provenance is inconsistent")
    native_dir = sealed.parent / "native"
    native_result = native_dir / "native-result.json"
    vi_trace = native_dir / "retrace-hashes.jsonl"
    update_trace = native_dir / "retrace-hashes.jsonl.updates.jsonl"
    if (not native_result.is_file() or not vi_trace.is_file() or
            not update_trace.is_file() or
            result.get("native_result_sha256") != file_sha256(native_result) or
            result.get("native_trace_sha256") != file_sha256(update_trace)):
        raise SupervisorError("determinism baseline native traces changed")
    native = json.loads(native_result.read_text(encoding="utf-8"))
    execution.check_native(packet, native)
    if (native.get("probe_target_reached") is not True or
            native.get("completed_update_trace_complete") is not True or
            native.get("target_retraces") != packet["native_target"] or
            native.get("executable_sha256") != job["spec"]["pins"]["native_sha256"] or
            type(native.get("completed_update_count")) is not int or
            native["completed_update_count"] < 1):
        raise SupervisorError("determinism baseline native completion is invalid")
    source = Path(packet["source_export"])
    manifest = json.loads((source / "export-manifest.json").read_text(encoding="utf-8"))
    initial = manifest.get("initial_state") or {}
    if (native.get("input_sha256") != manifest.get("input_sha256") or
            native.get("initial_flash_sha256") != initial.get("flash_sha256") or
            native.get("initial_pak_sha256") != initial.get("pak_sha256")):
        raise SupervisorError("determinism baseline input/initial state changed")
    return {"job": job, "packet": packet, "result": result, "sealed": sealed,
            "native": native, "native_result": native_result,
            "vi_trace": vi_trace, "update_trace": update_trace}


def pins(packet: dict[str, Any], repo: Path) -> dict[str, str]:
    return {"source_commit": packet["source_commit"],
            "tool_sha256": tool_sha256(repo),
            **{key + "_sha256": file_sha256(Path(packet["pin_files"][key]))
               for key in PIN_FILES}}


def validate(packet: dict[str, Any], repo: Path, state: Path) -> None:
    expected = {"schema", "job_id", "baseline_id", "source_commit", "pin_files",
                "source_export", "target_retraces", "completed_updates", "runs",
                "parallelism", "timeout_seconds", "evidence_files"}
    if (not isinstance(packet, dict) or not expected <= set(packet) or
            not set(packet) <= expected | {"execution"} or packet["schema"] != 1):
        raise SupervisorError("invalid determinism packet schema")
    execution.validate(packet)
    if any(not isinstance(packet[key], str) or not ID_RE.fullmatch(packet[key])
           for key in ("job_id", "baseline_id")):
        raise SupervisorError("invalid determinism job IDs")
    if (not isinstance(packet["source_commit"], str) or
            not len(packet["source_commit"]) in (40, 64) or
            not isinstance(packet["pin_files"], dict) or
            set(packet["pin_files"]) != set(PIN_FILES)):
        raise SupervisorError("invalid determinism source/binary pins")
    for key in PIN_FILES:
        if not isinstance(packet["pin_files"][key], str):
            raise SupervisorError("determinism binary pin is not a path")
        path = Path(packet["pin_files"][key])
        if not path.is_absolute() or not path.is_file():
            raise SupervisorError("determinism binary pin is missing")
    if not isinstance(packet["source_export"], str):
        raise SupervisorError("determinism export is not a path")
    source = Path(packet["source_export"])
    if (not source.is_absolute() or not source.is_dir() or
            not _inside(source, repo / "tools" / "private")):
        raise SupervisorError("determinism export must be private")
    if (type(packet["target_retraces"]) is not int or
            not 3 <= packet["target_retraces"] <= 1_000_000 or
            type(packet["completed_updates"]) is not int or
            not 1 <= packet["completed_updates"] <= 1_000_000 or
            type(packet["runs"]) is not int or not 2 <= packet["runs"] <= 100 or
            type(packet["parallelism"]) is not int or
            not 1 <= packet["parallelism"] <= min(8, packet["runs"]) or
            type(packet["timeout_seconds"]) is not int or
            not 60 <= packet["timeout_seconds"] <= 1800):
        raise SupervisorError("determinism run limits are invalid")
    files = packet["evidence_files"]
    if not isinstance(files, list) or len(files) != 7:
        raise SupervisorError("determinism evidence list is incomplete")
    for item in files:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"} or
                not isinstance(item["path"], str) or
                not isinstance(item["sha256"], str) or
                not SHA256_RE.fullmatch(item["sha256"])):
            raise SupervisorError("invalid determinism evidence pin")
        path = Path(item["path"])
        if (not path.is_absolute() or not path.is_file() or
                not (_inside(path, repo / "tools" / "private") or
                     _inside(path, state)) or
                file_sha256(path) != item["sha256"]):
            raise SupervisorError("determinism evidence changed")


def queue_determinism(store: JobStore, repo: Path, state: Path,
                      baseline_id: str, *, runs: int = 100,
                      parallelism: int = 4) -> str:
    context = _baseline(store, repo, state, baseline_id)
    baseline = context["packet"]
    source = Path(baseline["source_export"])
    job_id = determinism_id(
        file_sha256(source / "export-manifest.json"),
        context["job"]["spec"]["pins"]["native_sha256"],
        baseline["source_commit"], baseline["native_target"], runs,
        parallelism, baseline.get("execution"))
    evidence = [context["sealed"], context["vi_trace"], context["update_trace"]]
    evidence.extend(source / name for name in EVIDENCE_NAMES)
    packet = {
        "schema": 1, "job_id": job_id, "baseline_id": baseline_id,
        "source_commit": baseline["source_commit"],
        "pin_files": baseline["pin_files"],
        "source_export": baseline["source_export"],
        "target_retraces": baseline["native_target"],
        "completed_updates": context["native"]["completed_update_count"],
        "runs": runs, "parallelism": parallelism,
        "timeout_seconds": 300,
        "evidence_files": [{"path": str(path), "sha256": file_sha256(path)}
                           for path in evidence],
    }
    if "execution" in baseline:
        packet["execution"] = dict(baseline["execution"])
    validate(packet, repo, state)
    encoded = canonical_bytes(packet)
    directory = state / "determinism-packets"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (packet["job_id"] + ".json")
    if path.exists() and path.read_bytes() != encoded:
        raise SupervisorError("determinism job ID already names another packet")
    if not path.exists():
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
    digest = hashlib.sha256(encoded).hexdigest()
    store.enqueue(JobSpec(packet["job_id"], pins(packet, repo),
                          ("determinism-packet:" + digest,), (baseline_id,),
                          "native:determinism", 1, "json_complete"))
    return packet["job_id"]


def _run_summary(run_dir: Path, packet: dict[str, Any],
                 expected_pins: dict[str, str]) -> dict[str, Any]:
    result_path = run_dir / "native-result.json"
    vi_path = run_dir / "retrace-hashes.jsonl"
    update_path = run_dir / "retrace-hashes.jsonl.updates.jsonl"
    native = json.loads(result_path.read_text(encoding="utf-8"))
    execution.check_native(packet, native)
    source = Path(packet["source_export"])
    manifest = json.loads((source / "export-manifest.json").read_text(encoding="utf-8"))
    initial = manifest.get("initial_state") or {}
    if (native.get("exit_code") != 0 or
            native.get("probe_target_reached") is not True or
            native.get("completed_update_trace_complete") is not True or
            native.get("target_retraces") != packet["target_retraces"] or
            type(native.get("completed_update_count")) is not int or
            native["completed_update_count"] < 1 or
            native.get("executable_sha256") != expected_pins["native_sha256"] or
            native.get("rom_sha256") != expected_pins["rom_sha256"] or
            native.get("input_sha256") != manifest.get("input_sha256") or
            native.get("initial_flash_sha256") != initial.get("flash_sha256") or
            native.get("initial_pak_sha256") != initial.get("pak_sha256") or
            not isinstance(native.get("final_state_hash"), str) or
            not SHA256_RE.fullmatch(native["final_state_hash"]) or
            not vi_path.is_file() or not update_path.is_file()):
        raise SupervisorError("native repeat lacks pinned completed traces")
    return {"native_result_sha256": file_sha256(result_path),
            "vi_trace_sha256": file_sha256(vi_path),
            "update_trace_sha256": file_sha256(update_path),
            "final_state_hash": native.get("final_state_hash"),
            "completed_updates": native["completed_update_count"]}


def _recover(store: JobStore, lease: dict[str, Any], prior: Path,
             packet: dict[str, Any]) -> bool:
    result_path = prior / "result.json"
    if not result_path.is_file():
        return False
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("complete") is not True:
        return False
    digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    summaries = result.get("run_summaries")
    baseline_result_path = Path(packet["evidence_files"][0]["path"])
    baseline_result = json.loads(baseline_result_path.read_text(encoding="utf-8"))
    baseline_native_path = baseline_result_path.parent / "native" / "native-result.json"
    if baseline_result.get("native_result_sha256") != file_sha256(baseline_native_path):
        raise SupervisorError("expired determinism baseline native result changed")
    baseline_native = json.loads(baseline_native_path.read_text(encoding="utf-8"))
    if (result.get("kind") != "native-determinism" or
            result.get("job_id") != lease["job_id"] or
            result.get("packet_sha256") != digest or
            result.get("pins") != lease["spec"]["pins"] or
            not isinstance(summaries, list) or len(summaries) != packet["runs"] or
            any(_run_summary(prior / "runs" / f"{index:04d}", packet,
                             lease["spec"]["pins"]) != summary
                for index, summary in enumerate(summaries, 1))):
        raise SupervisorError("expired determinism bundle is inconsistent")
    first_different = next((index for index, summary in enumerate(summaries, 1)
                            if (summary["completed_updates"] !=
                                packet["completed_updates"] or
                                summary["vi_trace_sha256"] !=
                                packet["evidence_files"][1]["sha256"] or
                                summary["update_trace_sha256"] !=
                                packet["evidence_files"][2]["sha256"] or
                                summary["final_state_hash"] !=
                                baseline_native.get("final_state_hash"))), None)
    difference_path = prior / "first-difference.json"
    if (result.get("first_different_run") != first_different or
            result.get("deterministic") is not (first_different is None) or
            result.get("parity_verified") is not False or
            (first_different is None and
             (difference_path.exists() or result.get("first_difference_sha256") is not None)) or
            (first_different is not None and
             (not difference_path.is_file() or
              result.get("first_difference_sha256") != file_sha256(difference_path)))):
        raise SupervisorError("expired determinism classification changed")
    store.start(lease["job_id"], lease["token"])
    store.verify(lease["job_id"], lease["token"])
    store.seal_artifact(lease["job_id"], lease["token"], result_path)
    store.pass_job(lease["job_id"], lease["token"])
    return True


def run_determinism_lease(store: JobStore, lease: dict[str, Any],
                          repo: Path, state: Path) -> str:
    job_id, token, attempt = lease["job_id"], lease["token"], lease["attempt"]
    attempt_dir = state / "attempts" / job_id / f"{attempt:04d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    result_path = attempt_dir / "result.json"
    try:
        packet = json.loads((state / "determinism-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        validate(packet, repo, state)
        execution.require_current(packet)
        digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (lease["spec"]["inputs"] != ["determinism-packet:" + digest] or
                lease["spec"]["prerequisites"] != [packet["baseline_id"]] or
                pins(packet, repo) != lease["spec"]["pins"]):
            raise SupervisorError("determinism packet or tool pins changed")
        context = _baseline(store, repo, state, packet["baseline_id"])
        baseline_native_sha256 = file_sha256(context["native_result"])
        expected_evidence = ([context["sealed"], context["vi_trace"],
                              context["update_trace"]] +
                             [Path(packet["source_export"]) / name
                              for name in EVIDENCE_NAMES])
        if (packet["source_commit"] != context["packet"]["source_commit"] or
                packet.get("execution") != context["packet"].get("execution") or
                packet["pin_files"] != context["packet"]["pin_files"] or
                packet["source_export"] != context["packet"]["source_export"] or
                packet["target_retraces"] != context["packet"]["native_target"] or
                packet["completed_updates"] !=
                    context["native"]["completed_update_count"] or
                packet["evidence_files"] !=
                    [{"path": str(path), "sha256": file_sha256(path)}
                     for path in expected_evidence]):
            raise SupervisorError("determinism baseline evidence changed")
        for previous in store.attempt_history(job_id):
            if previous["number"] >= attempt or previous["outcome"] != "expired":
                continue
            prior = state / "attempts" / job_id / f"{previous['number']:04d}"
            if list(prior.glob("*.guard.json")) or (prior / "result.json").is_file():
                if not expired_attempt_contained(prior):
                    raise SupervisorError("expired native repeat may still have a live child")
                if _recover(store, lease, prior, packet):
                    return f"{job_id}: prior determinism bundle recovered"
        store.start(job_id, token)
        summaries: list[dict[str, Any]] = []
        first_different = None
        for first in range(1, packet["runs"] + 1, packet["parallelism"]):
            indices = range(first, min(packet["runs"] + 1,
                                       first + packet["parallelism"]))
            with ThreadPoolExecutor(max_workers=packet["parallelism"]) as pool:
                futures = {}
                for index in indices:
                    run_dir = attempt_dir / "runs" / f"{index:04d}"
                    run_dir.parent.mkdir(parents=True, exist_ok=True)
                    command = [real_python_executable(), "-m",
                               "scripts.phase95_native_replay",
                               packet["source_export"], str(run_dir),
                               "--executable", packet["pin_files"]["native"],
                               "--rom", packet["pin_files"]["rom"],
                               "--rom-sha256", lease["spec"]["pins"]["rom_sha256"],
                               "--target-retraces", str(packet["target_retraces"]),
                               "--update-hashes", "--timeout",
                               str(packet["timeout_seconds"] - 20)]
                    command += execution.cli(packet)
                    future = pool.submit(
                        bounded_command, command, repo,
                        attempt_dir / f"run-{index:04d}.stdout",
                        attempt_dir / f"run-{index:04d}.stderr",
                        time.monotonic() + packet["timeout_seconds"],
                        lambda: None, state / "PAUSED",
                        guard_record=attempt_dir / f"run-{index:04d}.guard.json",
                        max_output_bytes=4 * 1024 * 1024)
                    futures[future] = index
                pending = set(futures)
                failures = []
                while pending:
                    done, pending = wait(pending, timeout=5,
                                         return_when=FIRST_COMPLETED)
                    store.heartbeat(job_id, token, ttl=120)
                    for future in done:
                        code, reason = future.result()
                        if code != 0 or reason:
                            failures.append(futures[future])
                if failures:
                    raise SupervisorError("bounded native repeats failed: " +
                                          ",".join(map(str, sorted(failures))))
            for index in indices:
                run_dir = attempt_dir / "runs" / f"{index:04d}"
                summary = _run_summary(run_dir, packet, lease["spec"]["pins"])
                summaries.append(summary)
                if (first_different is None and
                        (summary["completed_updates"] !=
                         packet["completed_updates"] or
                         summary["vi_trace_sha256"] !=
                         packet["evidence_files"][1]["sha256"] or
                         summary["update_trace_sha256"] !=
                         packet["evidence_files"][2]["sha256"] or
                         summary["final_state_hash"] !=
                         context["native"]["final_state_hash"])):
                    first_different = index
        diagnosis = None
        if first_different is not None:
            run_dir = attempt_dir / "runs" / f"{first_different:04d}"
            vi_report, _ = compare_retraces(
                run_dir / "retrace-hashes.jsonl", context["vi_trace"], 0)
            update_report = compare_updates(
                run_dir / "retrace-hashes.jsonl.updates.jsonl",
                context["update_trace"], packet["completed_updates"])
            diagnosis = {"first_different_run": first_different,
                         "vi_comparison": vi_report,
                         "update_comparison": update_report}
            _write_json_atomic(attempt_dir / "first-difference.json", diagnosis)
        validate(packet, repo, state)
        execution.require_current(packet)
        if pins(packet, repo) != lease["spec"]["pins"]:
            raise SupervisorError("determinism tool or input pins changed during run")
        refreshed = _baseline(store, repo, state, packet["baseline_id"])
        if (file_sha256(refreshed["native_result"]) !=
                baseline_native_sha256 or
                refreshed["native"] != context["native"]):
            raise SupervisorError("determinism baseline native result changed during run")
        _write_json_atomic(result_path, {
            "schema": 1, "complete": True, "kind": "native-determinism",
            "job_id": job_id, "attempt": attempt, "packet_sha256": digest,
            "pins": lease["spec"]["pins"], "runs": packet["runs"],
            "parallelism": packet["parallelism"],
            "target_retraces": packet["target_retraces"],
            "baseline_vi_sha256": packet["evidence_files"][1]["sha256"],
            "baseline_update_sha256": packet["evidence_files"][2]["sha256"],
            "run_summaries": summaries,
            "first_different_run": first_different,
            "first_difference_sha256": file_sha256(attempt_dir / "first-difference.json")
                if diagnosis is not None else None,
            "deterministic": first_different is None,
            "parity_verified": False,
        })
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, result_path)
        store.pass_job(job_id, token)
        return f"{job_id}: {packet['runs']} native repeats sealed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        _write_json_atomic(result_path, {
            "schema": 1, "complete": False, "kind": "native-determinism",
            "job_id": job_id, "attempt": attempt,
            "stop_reason": str(error)[:300],
        })
        try:
            store.fail_job(job_id, token, str(error)[:300],
                           blocked=isinstance(error, SupervisorError))
        except JobStoreError:
            pass
        return f"{job_id}: determinism blocked ({error})"
