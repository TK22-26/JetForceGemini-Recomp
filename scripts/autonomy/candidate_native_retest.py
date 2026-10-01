"""Build a reviewed candidate and compare its native replay to a sealed oracle.

This is a raw completed-update regression diagnostic. Input/clock alignment
and full-game parity are separate gates, even when the raw prefix matches.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any

from scripts.autonomy.candidate_review import sealed_candidate
from scripts.autonomy.job_store import ID_RE, JobSpec, JobStore, JobStoreError, SHA256_RE
from scripts.autonomy.process_guard import real_python_executable
from scripts.autonomy.supervisor import (
    PIN_FILES, REVIEW_SCHEMA_FILE, SupervisorError, _git_ok, _inside,
    _write_json_atomic, bounded_command, canonical_bytes,
    expired_attempt_contained, file_sha256, read_packet, read_review,
    validate_candidate_build,
    validate_review_receipts,
)
from scripts.autonomy.update_job import validate as validate_update_packet
from scripts.autonomy import execution_contract as execution
from scripts.phase95_bridge import runtime_digest
from scripts.compare_phase9_update_hashes import compare
from scripts.phase95_poll_compare import (
    compare as compare_polls, native_polls, oracle_polls,
)


TOOL_FILES = (
    "scripts/autonomy/atomic_file.py",
    "scripts/autonomy/candidate_native_retest.py",
    "scripts/autonomy/execution_contract.py",
    "scripts/autonomy/source_build.py",
    "scripts/autonomy/source_snapshot.py",
    "scripts/autonomy/update_job.py",
    "scripts/phase95_bridge.py",
    "scripts/autonomy/supervisor.py",
    "scripts/phase95_native_replay.py",
    "scripts/phase9_point_probe.py",
    "scripts/compare_phase9_update_hashes.py",
    "scripts/compare_phase9_retrace_hashes.py",
    "scripts/phase95_poll_compare.py",
)


def tool_sha256(repo: Path) -> str:
    digest = hashlib.sha256()
    for relative in TOOL_FILES:
        digest.update(relative.encode("ascii"))
        digest.update(bytes.fromhex(file_sha256(repo / relative)))
    return digest.hexdigest()


def retest_id(review_id: str) -> str:
    candidate = review_id + "-native-retest"
    if len(candidate) <= 128:
        return candidate
    return "native-retest-" + hashlib.sha256(review_id.encode("ascii")).hexdigest()[:24]


def worktree_path(state: Path, job_id: str, attempt: int) -> Path:
    """Keep Git's Windows checkout below legacy MAX_PATH for deep fixtures."""
    key = hashlib.sha256(job_id.encode("ascii")).hexdigest()[:20]
    return state / "w" / key / f"{attempt:04d}"


def build_path(state: Path, job_id: str, attempt: int) -> Path:
    """MSBuild's nested dependency trees also require a short build root."""
    key = hashlib.sha256(job_id.encode("ascii")).hexdigest()[:20]
    return state / "b" / key / f"{attempt:04d}"


def _sealed_result(store: JobStore, state: Path, job_id: str,
                   prefix: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
    job = store.job(job_id)
    if (job["state"] != "passed" or not job["spec"]["inputs"] or
            not job["spec"]["inputs"][0].startswith(prefix) or
            not job["sealed_artifact"] or not job["sealed_sha256"]):
        raise SupervisorError("candidate retest prerequisite is not sealed")
    sealed = Path(job["sealed_artifact"]).resolve(strict=True)
    if (not sealed.is_relative_to((state / "attempts" / job_id).resolve()) or
            sealed.name != "result.json" or
            file_sha256(sealed) != job["sealed_sha256"]):
        raise SupervisorError("candidate retest prerequisite seal changed")
    result = json.loads(sealed.read_text(encoding="utf-8"))
    if result.get("complete") is not True or result.get("job_id") != job_id:
        raise SupervisorError("candidate retest prerequisite is incomplete")
    return job, result, sealed


def verified_context(store: JobStore, repo: Path, state: Path,
                     review_id: str) -> dict[str, Any] | None:
    """Return approved review + matching update baseline, or no recipe."""
    review_job, review, review_seal = _sealed_result(
        store, state, review_id, "packet:")
    review_packet = read_packet(state / "packets" / (review_id + ".json"), repo)
    review_packet_sha = hashlib.sha256(canonical_bytes(review_packet)).hexdigest()
    if (review_packet["kind"] != "review" or
            review_job["spec"]["inputs"] != ["packet:" + review_packet_sha] or
            review_job["spec"]["prerequisites"] != review_packet["prerequisites"] or
            review.get("packet_sha256") != review_packet_sha or
            review.get("pins") != review_job["spec"]["pins"] or
            review.get("candidate_only") is not True or
            review.get("review_schema_sha256") != file_sha256(REVIEW_SCHEMA_FILE)):
        raise SupervisorError("review provenance is inconsistent")
    review_output = review_seal.parent / "last-message.txt"
    verdict = read_review(review_output)
    if review.get("review_sha256") != file_sha256(review_output):
        raise SupervisorError("review verdict changed after sealing")
    if verdict["verdict"] != "approve":
        return None
    validate_review_receipts(review, review_seal.parent)
    implementation_id = review_packet["prerequisites"][0]
    implementation_packet, _, implementation_seal = sealed_candidate(
        store, repo, state, implementation_id)
    recipe = implementation_packet.get("candidate_build")
    if recipe is None:
        return None
    validate_candidate_build(recipe)
    candidate_commit = review.get("candidate_commit")
    if (not isinstance(candidate_commit, str) or
            len(candidate_commit) not in (40, 64) or
            review.get("candidate_result_sha256") !=
                file_sha256(implementation_seal) or
            _git_ok(repo, "rev-parse", "--verify",
                    candidate_commit + "^{commit}") != candidate_commit or
            _git_ok(repo, "rev-parse", candidate_commit + "^") !=
                implementation_packet["source_commit"]):
        raise SupervisorError("reviewed candidate commit is not the pinned descendant")
    retest_checks = review.get("candidate_retest_validation")
    if (not isinstance(retest_checks, list) or
            len(retest_checks) != len(implementation_packet["validation"]) or
            any(not isinstance(check, dict) or check.get("argv") != argv or
                check.get("exit_code") != 0 or check.get("stop_reason") is not None
                for check, argv in zip(retest_checks,
                                       implementation_packet["validation"]))):
        raise SupervisorError("reviewed candidate validation is incomplete")
    baseline_id = recipe["baseline_update_id"]
    baseline_job, baseline, baseline_seal = _sealed_result(
        store, state, baseline_id, "update-packet:")
    baseline_packet = json.loads((state / "update-packets" /
                                  (baseline_id + ".json")).read_text(encoding="utf-8"))
    validate_update_packet(baseline_packet, repo)
    execution.require_current(baseline_packet)
    baseline_packet_sha = hashlib.sha256(canonical_bytes(baseline_packet)).hexdigest()
    if (baseline_job["spec"]["inputs"] != ["update-packet:" + baseline_packet_sha] or
            baseline.get("packet_sha256") != baseline_packet_sha or
            baseline.get("pins") != baseline_job["spec"]["pins"] or
            baseline_job["spec"]["pins"]["source_commit"] !=
                baseline_packet["source_commit"] or
            any(baseline_job["spec"]["pins"][key + "_sha256"] !=
                file_sha256(Path(baseline_packet["pin_files"][key]))
                for key in PIN_FILES) or
            baseline.get("kind") != "update-execution" or
            baseline.get("parity_verified") is not False or
            baseline.get("input_prefix_match") is not True or
            baseline_packet["source_commit"] != implementation_packet["source_commit"] or
            baseline_packet["pin_files"] != implementation_packet["pin_files"]):
        raise SupervisorError("candidate and baseline do not share pinned source/input")
    native_trace = baseline_seal.parent / "native" / "retrace-hashes.jsonl.updates.jsonl"
    native_result_path = baseline_seal.parent / "native" / "native-result.json"
    oracle_trace = baseline_seal.parent / "oracle" / "update-hashes.jsonl"
    report_path = baseline_seal.parent / "update-comparison.json"
    if (not native_result_path.is_file() or
            baseline.get("native_result_sha256") != file_sha256(native_result_path) or
            not native_trace.is_file() or not oracle_trace.is_file() or
            not report_path.is_file() or
            baseline.get("native_trace_sha256") != file_sha256(native_trace) or
            baseline.get("oracle_trace_sha256") != file_sha256(oracle_trace) or
            baseline.get("comparison_sha256") != file_sha256(report_path)):
        raise SupervisorError("baseline update traces or comparison changed")
    baseline_report = json.loads(report_path.read_text(encoding="utf-8"))
    baseline_native = json.loads(native_result_path.read_text(encoding="utf-8"))
    execution.check_native(baseline_packet, baseline_native)
    oracle_result_path = baseline_seal.parent / "oracle" / "oracle-result.json"
    if "execution" in baseline_packet:
        if baseline.get("oracle_result_sha256") != file_sha256(oracle_result_path):
            raise SupervisorError("baseline oracle runtime report changed")
        execution.check_oracle(baseline_packet, json.loads(
            oracle_result_path.read_text(encoding="utf-8")))
    update_count = baseline_native.get("completed_update_count")
    if (baseline_report.get("kind") != "jfg-phase9-update-comparison" or
            baseline_report.get("scope") != "prefix" or
            type(update_count) is not int or not 1 <= update_count <= 1_000_000 or
            baseline_report.get("requested_updates") != update_count or
            baseline_native.get("target_retraces") != baseline_packet["native_target"] or
            baseline_report.get("match") is not baseline.get("prefix_match") or
            baseline_report.get("first_divergence") != baseline.get("first_divergence") or
            type(baseline_packet.get("native_target")) is not int or
            baseline_packet["native_target"] < 3):
        raise SupervisorError("baseline update report is inconsistent")
    return {"review_id": review_id, "review": review,
            "review_seal": review_seal, "implementation_packet": implementation_packet,
            "baseline_id": baseline_id, "baseline": baseline,
            "baseline_seal": baseline_seal, "baseline_packet": baseline_packet,
            "candidate_commit": candidate_commit, "recipe": recipe,
            "native_trace": native_trace, "oracle_trace": oracle_trace,
            "baseline_update_count": update_count}


def pins(packet: dict[str, Any], repo: Path) -> dict[str, str]:
    return {"source_commit": packet["candidate_commit"],
            "tool_sha256": tool_sha256(repo),
            **{key + "_sha256": file_sha256(Path(packet["pin_files"][key]))
               for key in PIN_FILES}}


def validate(packet: dict[str, Any], repo: Path) -> None:
    required = {"schema", "job_id", "review_id", "baseline_update_id",
                "candidate_commit", "pin_files", "recipe",
                "review_result_sha256", "baseline_result_sha256",
                "native_trace_sha256", "oracle_trace_sha256",
                "source_export", "target_retraces", "target_updates"}
    if (not isinstance(packet, dict) or not required <= set(packet) or
            not set(packet) <= required | {"execution"} or packet["schema"] != 1):
        raise SupervisorError("candidate retest packet schema is invalid")
    execution.validate(packet)
    if any(not isinstance(packet[key], str) or not ID_RE.fullmatch(packet[key])
           for key in ("job_id", "review_id", "baseline_update_id")):
        raise SupervisorError("candidate retest job IDs are invalid")
    if (not isinstance(packet["candidate_commit"], str) or
            len(packet["candidate_commit"]) not in (40, 64) or
            _git_ok(repo, "rev-parse", "--verify",
                    packet["candidate_commit"] + "^{commit}") !=
                packet["candidate_commit"]):
        raise SupervisorError("candidate retest commit is invalid")
    if (not isinstance(packet["pin_files"], dict) or
            set(packet["pin_files"]) != set(PIN_FILES)):
        raise SupervisorError("candidate retest binary pins are incomplete")
    for key in PIN_FILES:
        value = packet["pin_files"][key]
        if not isinstance(value, str) or not Path(value).is_absolute() or not Path(value).is_file():
            raise SupervisorError("candidate retest binary pin is missing")
    validate_candidate_build(packet["recipe"])
    if packet["recipe"]["baseline_update_id"] != packet["baseline_update_id"]:
        raise SupervisorError("candidate retest recipe changed baseline")
    if any(not isinstance(packet[key], str) or not SHA256_RE.fullmatch(packet[key])
           for key in ("review_result_sha256", "baseline_result_sha256",
                       "native_trace_sha256", "oracle_trace_sha256")):
        raise SupervisorError("candidate retest evidence hashes are invalid")
    source = packet["source_export"]
    if (not isinstance(source, str) or not Path(source).is_absolute() or
            not Path(source).is_dir() or
            not _inside(Path(source), repo / "tools" / "private")):
        raise SupervisorError("candidate retest export must be private")
    if (type(packet["target_retraces"]) is not int or
            not 3 <= packet["target_retraces"] <= 1_000_000 or
            type(packet["target_updates"]) is not int or
            not 1 <= packet["target_updates"] <= 1_000_000):
        raise SupervisorError("candidate retest targets are invalid")


def queue_retest(store: JobStore, repo: Path, state: Path, review_id: str) -> str | None:
    context = verified_context(store, repo, state, review_id)
    if context is None:
        return None
    baseline_packet = context["baseline_packet"]
    packet = {
        "schema": 1, "job_id": retest_id(review_id),
        "review_id": review_id, "baseline_update_id": context["baseline_id"],
        "candidate_commit": context["candidate_commit"],
        "pin_files": baseline_packet["pin_files"], "recipe": context["recipe"],
        "review_result_sha256": file_sha256(context["review_seal"]),
        "baseline_result_sha256": file_sha256(context["baseline_seal"]),
        "native_trace_sha256": file_sha256(context["native_trace"]),
        "oracle_trace_sha256": file_sha256(context["oracle_trace"]),
        "source_export": baseline_packet["source_export"],
        "target_retraces": baseline_packet["native_target"],
        "target_updates": context["baseline_update_count"],
    }
    if "execution" in baseline_packet:
        packet["execution"] = dict(baseline_packet["execution"])
    validate(packet, repo)
    encoded = canonical_bytes(packet)
    packet_dir = state / "candidate-retest-packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    path = packet_dir / (packet["job_id"] + ".json")
    if path.exists() and path.read_bytes() != encoded:
        raise SupervisorError("candidate retest ID already names a different packet")
    if not path.exists():
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
    digest = hashlib.sha256(encoded).hexdigest()
    store.enqueue(JobSpec(packet["job_id"], pins(packet, repo),
                          ("candidate-retest-packet:" + digest,),
                          (review_id, context["baseline_id"]),
                          "build:native", 1, "json_complete"))
    return packet["job_id"]


def expand_command(argv: list[str], worktree: Path, build_dir: Path) -> list[str]:
    expanded = [arg.replace("{source}", str(worktree)).replace(
        "{build}", str(build_dir)) for arg in argv]
    if any(re.search(r"\{[^{}]*\}", arg) for arg in expanded):
        raise SupervisorError("candidate build command has unknown placeholders")
    return expanded


def raw_frontier(baseline: dict[str, Any], candidate: dict[str, Any],
                 target: int) -> dict[str, Any]:
    """Classify first raw mismatch movement without a parity claim."""
    def first(report: dict[str, Any]) -> int:
        if report.get("match") is True and report.get("compared_updates") == target:
            return target + 1
        divergence = report.get("first_divergence")
        if (not isinstance(divergence, dict) or
                type(divergence.get("update")) is not int or
                not 1 <= divergence["update"] <= target):
            raise SupervisorError("raw comparison lacks a bounded first mismatch")
        return divergence["update"]
    old, new = first(baseline), first(candidate)
    return {"baseline_first_raw_mismatch": None if old > target else old,
            "candidate_first_raw_mismatch": None if new > target else new,
            "classification": ("moved-later" if new > old else
                               "regressed-earlier" if new < old else "unchanged"),
            "no_earlier_raw_mismatch": new >= old,
            "alignment_validated": False, "parity_verified": False}


def candidate_disposition(frontier: dict[str, Any], input_match: bool) -> str:
    """Retain or reject this diagnostic candidate; never merge or claim parity."""
    if type(input_match) is not bool or frontier.get("classification") not in (
            "moved-later", "regressed-earlier", "unchanged"):
        raise SupervisorError("candidate disposition needs a bounded replay comparison")
    if not input_match:
        return "rejected-input-mismatch"
    if frontier["classification"] == "regressed-earlier":
        return "rejected-regression"
    if frontier["classification"] == "unchanged":
        return "retained-no-frontier-gain"
    return "retained-for-integration-review"


def _recover(store: JobStore, lease: dict[str, Any], prior: Path,
             packet: dict[str, Any], state: Path, prior_attempt: int) -> bool:
    path = prior / "result.json"
    if not path.is_file():
        return False
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("complete") is not True:
        return False
    digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    report_path = prior / "candidate-comparison.json"
    baseline_path = prior / "baseline-comparison.json"
    poll_path = prior / "input-poll-comparison.json"
    native_result = prior / "native" / "native-result.json"
    native_trace = prior / "native" / "retrace-hashes.jsonl.updates.jsonl"
    build_dir = build_path(state, lease["job_id"], prior_attempt)
    executable = build_dir / packet["recipe"]["executable"]
    files = {"comparison_sha256": report_path,
             "baseline_comparison_sha256": baseline_path,
             "input_poll_comparison_sha256": poll_path,
             "native_result_sha256": native_result,
             "native_trace_sha256": native_trace,
             "candidate_executable_sha256": executable}
    if (result.get("kind") != "candidate-native-update-retest" or
            result.get("job_id") != lease["job_id"] or
            result.get("packet_sha256") != digest or
            result.get("pins") != lease["spec"]["pins"] or
            result.get("candidate_commit") != packet["candidate_commit"] or
            result.get("candidate_only") is not True or
            result.get("alignment_validated") is not False or
            result.get("parity_verified") is not False or
            not _inside(executable, build_dir) or
            any(not file.is_file() or result.get(key) != file_sha256(file)
                for key, file in files.items())):
        raise SupervisorError("expired candidate retest bundle is inconsistent")
    candidate_runtime = runtime_digest(executable.parent)
    execution.check_native(packet, json.loads(native_result.read_text(encoding="utf-8")),
                           candidate_runtime=candidate_runtime)
    if ("execution" in packet and
            result.get("candidate_runtime_sha256") != candidate_runtime):
        raise SupervisorError("expired candidate runtime changed")
    candidate_report = json.loads(report_path.read_text(encoding="utf-8"))
    baseline_report = json.loads(baseline_path.read_text(encoding="utf-8"))
    frontier = raw_frontier(baseline_report, candidate_report,
                            packet["target_updates"])
    poll = json.loads(poll_path.read_text(encoding="utf-8"))
    if (result.get("raw_frontier") != frontier or
            result.get("input_prefix_match") is not
                (poll.get("first_input_mismatch") is None) or
            result.get("compared_polls") != poll.get("shared_prefix_polls")):
        raise SupervisorError("expired candidate retest report changed")
    if ("candidate_disposition" in result and result["candidate_disposition"] !=
            candidate_disposition(frontier, poll.get("first_input_mismatch") is None)):
        raise SupervisorError("expired candidate disposition differs from replay evidence")
    store.start(lease["job_id"], lease["token"])
    store.verify(lease["job_id"], lease["token"])
    store.seal_artifact(lease["job_id"], lease["token"], path)
    store.pass_job(lease["job_id"], lease["token"])
    return True


def run_retest_lease(store: JobStore, lease: dict[str, Any],
                     repo: Path, state: Path) -> str:
    job_id, token, attempt = lease["job_id"], lease["token"], lease["attempt"]
    attempt_dir = state / "attempts" / job_id / f"{attempt:04d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    result_path = attempt_dir / "result.json"
    worktree = worktree_path(state, job_id, attempt)
    try:
        packet = json.loads((state / "candidate-retest-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        validate(packet, repo)
        execution.require_current(packet)
        digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (lease["spec"]["inputs"] != ["candidate-retest-packet:" + digest] or
                lease["spec"]["prerequisites"] != [packet["review_id"],
                                                       packet["baseline_update_id"]] or
                pins(packet, repo) != lease["spec"]["pins"]):
            raise SupervisorError("candidate retest packet or tool pins changed")
        context = verified_context(store, repo, state, packet["review_id"])
        if (context is None or
                packet.get("execution") != context["baseline_packet"].get("execution") or
                packet["baseline_update_id"] != context["baseline_id"] or
                packet["candidate_commit"] != context["candidate_commit"] or
                packet["pin_files"] != context["baseline_packet"]["pin_files"] or
                packet["recipe"] != context["recipe"] or
                packet["source_export"] != context["baseline_packet"]["source_export"] or
                packet["target_retraces"] != context["baseline_packet"]["native_target"] or
                packet["target_updates"] != context["baseline_update_count"] or
                packet["review_result_sha256"] != file_sha256(context["review_seal"]) or
                packet["baseline_result_sha256"] != file_sha256(context["baseline_seal"]) or
                packet["native_trace_sha256"] != file_sha256(context["native_trace"]) or
                packet["oracle_trace_sha256"] != file_sha256(context["oracle_trace"])):
            raise SupervisorError("candidate retest prerequisites or evidence changed")
        for previous in store.attempt_history(job_id):
            if previous["number"] >= attempt or previous["outcome"] != "expired":
                continue
            prior = state / "attempts" / job_id / f"{previous['number']:04d}"
            prior_worktree = worktree_path(state, job_id, previous["number"])
            if prior_worktree.exists() or list(prior.glob("*.guard.json")) or \
                    (prior / "result.json").is_file():
                if not expired_attempt_contained(prior):
                    raise SupervisorError("expired candidate build may still have a live child")
                if _recover(store, lease, prior, packet, state,
                            previous["number"]):
                    return f"{job_id}: prior candidate retest recovered"
        if worktree.exists():
            raise SupervisorError("candidate retest worktree already exists")
        worktree.parent.mkdir(parents=True, exist_ok=True)
        _git_ok(repo, "worktree", "add", "--detach", str(worktree),
                packet["candidate_commit"])
        if not _inside(worktree, state) or _git_ok(worktree, "rev-parse", "HEAD") != \
                packet["candidate_commit"]:
            raise SupervisorError("candidate retest worktree identity is invalid")
        store.start(job_id, token)
        recipe = packet["recipe"]
        build_dir = build_path(state, job_id, attempt)
        if build_dir.exists():
            raise SupervisorError("candidate retest build directory already exists")
        build_dir.mkdir(parents=True)
        build_deadline = time.monotonic() + recipe["timeout_seconds"]
        heartbeat = lambda: store.heartbeat(job_id, token, ttl=120)
        checks = []
        for index, key in enumerate(("configure_argv", "build_argv")):
            command = expand_command(recipe[key], worktree, build_dir)
            code, reason = bounded_command(
                command, worktree, attempt_dir / f"build-{index}.stdout",
                attempt_dir / f"build-{index}.stderr", build_deadline,
                heartbeat, state / "PAUSED",
                guard_record=attempt_dir / f"build-{index}.guard.json")
            checks.append({"argv": command, "exit_code": code,
                           "stop_reason": reason})
            if code != 0 or reason:
                raise SupervisorError("bounded candidate CMake build failed")
        executable = (build_dir / recipe["executable"]).resolve()
        if not _inside(executable, build_dir) or not executable.is_file():
            raise SupervisorError("candidate build did not produce pinned executable path")
        if _git_ok(worktree, "status", "--porcelain"):
            raise SupervisorError("candidate build modified its reviewed source worktree")
        validate_candidate_build(recipe)
        if pins(packet, repo) != lease["spec"]["pins"]:
            raise SupervisorError("candidate retest inputs changed during build")
        native_dir = attempt_dir / "native"
        candidate_runtime = runtime_digest(executable.parent)
        replay_deadline = time.monotonic() + 900
        command = [real_python_executable(), "-m", "scripts.phase95_native_replay",
                   packet["source_export"], str(native_dir),
                   "--executable", str(executable), "--rom", packet["pin_files"]["rom"],
                   "--rom-sha256", lease["spec"]["pins"]["rom_sha256"],
                   "--target-retraces", str(packet["target_retraces"]),
                   "--update-hashes", "--poll-trace", "--timeout", "870"]
        command += execution.cli(packet)
        code, reason = bounded_command(
            command, repo, attempt_dir / "native.stdout",
            attempt_dir / "native.stderr", replay_deadline,
            heartbeat, state / "PAUSED",
            guard_record=attempt_dir / "native.guard.json")
        if code != 0 or reason:
            raise SupervisorError("bounded candidate native replay failed")
        native_result = native_dir / "native-result.json"
        native_trace = native_dir / "retrace-hashes.jsonl.updates.jsonl"
        native = json.loads(native_result.read_text(encoding="utf-8"))
        execution.check_native(packet, native, candidate_runtime=candidate_runtime)
        export = json.loads((Path(packet["source_export"]) /
                             "export-manifest.json").read_text(encoding="utf-8"))
        initial = export.get("initial_state") or {}
        if (native.get("exit_code") != 0 or
                native.get("probe_target_reached") is not True or
                native.get("completed_update_trace_complete") is not True or
                type(native.get("completed_update_count")) is not int or
                native["completed_update_count"] < 1 or
                native.get("source_export") != packet["source_export"] or
                native.get("target_retraces") != packet["target_retraces"] or
                native.get("rom_sha256") != lease["spec"]["pins"]["rom_sha256"] or
                native.get("executable_sha256") != file_sha256(executable) or
                native.get("input_sha256") != export.get("input_sha256") or
                native.get("initial_flash_sha256") != initial.get("flash_sha256") or
                native.get("initial_pak_sha256") != initial.get("pak_sha256") or
                not native_trace.is_file()):
            raise SupervisorError("candidate native replay lacks pinned completion")
        candidate_report = compare(native_trace, context["oracle_trace"],
                                   packet["target_updates"])
        baseline_report = compare(context["native_trace"],
                                  context["oracle_trace"], packet["target_updates"])
        if baseline_report["first_divergence"] != context["baseline"]["first_divergence"]:
            raise SupervisorError("baseline raw divergence moved without a candidate")
        frontier = raw_frontier(baseline_report, candidate_report,
                                packet["target_updates"])
        candidate_report_path = attempt_dir / "candidate-comparison.json"
        baseline_report_path = attempt_dir / "baseline-comparison.json"
        _write_json_atomic(candidate_report_path, candidate_report)
        _write_json_atomic(baseline_report_path, baseline_report)
        oracle_dir = context["baseline_seal"].parent / "oracle"
        compared_polls = min(len(oracle_polls(oracle_dir / "checkpoints.tsv")),
                             len(native_polls(native_dir / "controller-polls.tsv")),
                             export["controller_polls"])
        if compared_polls < 1:
            raise SupervisorError("candidate replay has no comparable input polls")
        poll_path = attempt_dir / "input-poll-comparison.json"
        poll_report = compare_polls(Path(packet["source_export"]), oracle_dir,
                                    native_dir, poll_path,
                                    prefix_polls=compared_polls)
        validate(packet, repo)
        execution.require_current(packet)
        if runtime_digest(executable.parent) != candidate_runtime:
            raise SupervisorError("candidate runtime changed during replay")
        if pins(packet, repo) != lease["spec"]["pins"]:
            raise SupervisorError("candidate retest inputs changed during replay")
        if (packet["native_trace_sha256"] != file_sha256(context["native_trace"]) or
                packet["oracle_trace_sha256"] != file_sha256(context["oracle_trace"]) or
                packet["baseline_result_sha256"] != file_sha256(context["baseline_seal"]) or
                packet["review_result_sha256"] != file_sha256(context["review_seal"])):
            raise SupervisorError("candidate retest baseline evidence changed during replay")
        _write_json_atomic(result_path, {
            "schema": 1, "complete": True,
            "kind": "candidate-native-update-retest",
            "job_id": job_id, "attempt": attempt, "packet_sha256": digest,
            "pins": lease["spec"]["pins"],
            "candidate_commit": packet["candidate_commit"],
            "candidate_only": True, "parity_verified": False,
            "alignment_validated": False,
            "candidate_executable_sha256": file_sha256(executable),
            "candidate_runtime_sha256": candidate_runtime,
            "native_result_sha256": file_sha256(native_result),
            "native_trace_sha256": file_sha256(native_trace),
            "comparison_sha256": file_sha256(candidate_report_path),
            "baseline_comparison_sha256": file_sha256(baseline_report_path),
            "input_poll_comparison_sha256": file_sha256(poll_path),
            "input_prefix_match": poll_report["first_input_mismatch"] is None,
            "compared_polls": poll_report["shared_prefix_polls"],
            "raw_frontier": frontier,
            "candidate_disposition": candidate_disposition(
                frontier, poll_report["first_input_mismatch"] is None),
            "build_checks": checks,
            "build_closure_verified": False,
        })
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, result_path)
        store.pass_job(job_id, token)
        return f"{job_id}: candidate native diagnostic sealed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        _write_json_atomic(result_path, {
            "schema": 1, "complete": False,
            "kind": "candidate-native-update-retest",
            "job_id": job_id, "attempt": attempt,
            "stop_reason": str(error)[:300],
        })
        try:
            store.fail_job(job_id, token, str(error)[:300],
                           blocked=isinstance(error, SupervisorError))
        except JobStoreError:
            pass
        return f"{job_id}: candidate retest blocked ({error})"
