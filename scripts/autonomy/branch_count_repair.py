"""Proof-gated intake for the independently qualified REGIMM Count defect.

One deliberately narrow repair policy, not permission to synthesize arbitrary
runtime edits from model text. The protected test must fail on frozen source
in exactly the measured cases before an implementation packet can be queued.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.autonomy import execution_contract, source_build
from scripts.autonomy.candidate_native_retest import _sealed_result
from scripts.autonomy.job_store import JobStore
from scripts.autonomy.process_guard import real_python_executable
from scripts.autonomy.supervisor import (
    SupervisorError, _write_json_atomic, canonical_bytes, enqueue_packet,
    file_sha256, read_diagnosis, read_packet, validate_candidate_build, validate_packet,
)
from scripts.autonomy.update_job import validate as validate_update
from scripts.phase9_branch_count_check import check
from scripts.phase9_cpu_branch_trace import parse_trace


POLICY = "regimm-annulled-count-v1"


def require_red_proof(proof):
    expected = [{"kind": kind, "taken": 0, "iterations": count,
                 "native_ticks": 8 * count + 2, "oracle_ticks": 10 * count + 2}
                for kind in (4, 5) for count in (16, 128)]
    if (proof.get("kind") != "jfg-native-branch-count-check" or
            proof.get("complete") is not True or proof.get("match") is not False or
            proof.get("cases") != 28 or proof.get("hardware_qualified") is not False or
            proof.get("game_cause_proved") is not False or proof.get("mismatches") != expected):
        raise SupervisorError("repair requires the exact four independently reproduced Count failures")


def require_oracle(report, trace: Path, contract):
    if (report.get("kind") != "jfg-phase9-cpu-branch-microtest" or
            report.get("complete") is not True or report.get("exit_code") != 0 or
            report.get("core") != "Mupen64Plus" or
            report.get("runtime_sha256") != contract["oracle_runtime_sha256"] or
            report.get("config_sha256") != contract["oracle_config_sha256"] or
            report.get("trace_sha256") != file_sha256(trace) or
            report.get("observed") != parse_trace(trace)):
        raise SupervisorError("branch micro does not match the pinned replay reference")


def recipe_from_build(report, baseline_id, executable, build_record_path):
    configure, build = report["commands"]
    source = configure[configure.index("-S") + 1]
    directory = configure[configure.index("-B") + 1]
    generated = next((arg.split("=", 1)[1] for arg in configure
                      if arg.startswith("-DJFG_GENERATED_ROOT=")), None)
    if generated is None:
        raise SupervisorError("repair build requires its recorded generated root")
    recipe = {
        "baseline_update_id": baseline_id,
        "configure_argv": ["{source}" if arg == source else "{build}" if arg == directory
                           else arg for arg in configure],
        "build_argv": ["{build}" if arg == directory else arg for arg in build],
        "executable": executable.resolve().relative_to(Path(directory).resolve()).as_posix(),
        "build_inputs": [source_build.pin(build_record_path),
                         source_build.pin(Path(generated) / "sources.json")],
        "timeout_seconds": 1200,
    }
    validate_candidate_build(recipe)
    return recipe


def register(repo, state, *, diagnosis_id, baseline_id, oracle_report, oracle_trace):
    case = {"schema": 1, "policy": POLICY, "diagnosis_id": diagnosis_id,
            "baseline_id": baseline_id, "oracle_report": source_build.pin(oracle_report),
            "oracle_trace": source_build.pin(oracle_trace)}
    identity = hashlib.sha256(canonical_bytes(case)).hexdigest()[:12]
    path = state / "repair-intake" / ("bc-" + identity + ".json")
    if path.exists() and json.loads(path.read_text()) != case:
        raise SupervisorError("repair intake identity collision")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(path, case)
    return path


def queue_case(store, repo, state, agent_binary, case_path):
    case = json.loads(case_path.read_text(encoding="utf-8"))
    if (set(case) != {"schema", "policy", "diagnosis_id", "baseline_id",
                     "oracle_report", "oracle_trace"} or
            case["schema"] != 1 or case["policy"] != POLICY):
        raise SupervisorError("unrecognized repair intake policy")
    identity = hashlib.sha256(canonical_bytes(case)).hexdigest()[:12]
    job_id = "bc-" + identity
    if job_id in {job["job_id"] for job in store.status_projection()["jobs"]}:
        return None  # One candidate per qualified intake, no unbounded retry loop.
    if (state / "PAUSED").exists():
        return None
    baseline_job, baseline, baseline_seal = _sealed_result(
        store, state, case["baseline_id"], "update-packet:")
    packet = json.loads((state / "update-packets" / (case["baseline_id"] + ".json")).read_text())
    validate_update(packet, repo)
    execution_contract.require_current(packet)
    packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    if (baseline_job["spec"]["inputs"] != ["update-packet:" + packet_sha] or
            baseline.get("packet_sha256") != packet_sha or
            baseline.get("pins") != baseline_job["spec"]["pins"] or
            baseline.get("input_prefix_match") is not True or
            packet.get("execution", {}).get("profile") != "original-os-probe" or
            "source_build" not in packet):
        raise SupervisorError("repair baseline lacks source/profile/input provenance")
    diagnostic_job, diagnostic, diagnostic_seal = _sealed_result(
        store, state, case["diagnosis_id"], "packet:")
    diagnostic_packet = read_packet(state / "packets" / (case["diagnosis_id"] + ".json"), repo)
    diagnostic_sha = hashlib.sha256(canonical_bytes(diagnostic_packet)).hexdigest()
    message = diagnostic_seal.parent / "last-message.txt"
    read_diagnosis(message)  # Schema only: a model claim is not the proof gate.
    if (diagnostic_packet["kind"] != "diagnose" or
            diagnostic_job["spec"]["inputs"] != ["packet:" + diagnostic_sha] or
            diagnostic.get("packet_sha256") != diagnostic_sha or
            diagnostic.get("pins") != diagnostic_job["spec"]["pins"] or
            diagnostic.get("diagnosis_sha256") != file_sha256(message) or
            diagnostic_packet["source_commit"] != packet["source_commit"] or
            diagnostic_packet["pin_files"] != packet["pin_files"] or
            case["baseline_id"] not in diagnostic_packet["prerequisites"]):
        raise SupervisorError("repair diagnosis is not tied to this frozen baseline")
    native = Path(packet["pin_files"]["native"])
    binding = source_build.validate(repo, packet["source_build"], native)
    build_record = Path(packet["source_build"]["path"])
    build_report = Path(binding["evidence"][0]["path"])
    build, source, _ = source_build.build_context(repo, build_report)
    source_file = source / "src/boot/native_boot.cpp"
    # Match immutable Git contents too, not only the build worktree's HEAD.
    from scripts.autonomy.source_snapshot import git
    source_bytes = git(repo, "show", packet["source_commit"] + ":src/boot/native_boot.cpp")
    if source_file.read_bytes() != source_bytes:
        raise SupervisorError("baseline source changed before independent red test")
    oracle_path = source_build.pinned_file(repo, case["oracle_report"])
    trace = source_build.pinned_file(repo, case["oracle_trace"])
    oracle = json.loads(oracle_path.read_text())
    require_oracle(oracle, trace, packet["execution"])
    proof = check(source_file, trace)
    require_red_proof(proof)
    proof_path = state / "repair-proofs" / (job_id + ".json")
    if proof_path.exists() and json.loads(proof_path.read_text()) != proof:
        raise SupervisorError("independent repair proof changed")
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(proof_path, proof)
    checker = repo / "scripts/phase9_branch_count_check.py"
    parser = repo / "scripts/phase9_cpu_branch_trace.py"
    evidence = [diagnostic_seal, message, baseline_seal, build_record, oracle_path,
                trace, proof_path, checker, parser, case_path.resolve()]
    implementation = {
        "schema": 1, "job_id": job_id, "kind": "implement",
        "source_commit": packet["source_commit"], "pin_files": packet["pin_files"],
        "prompt": (
            "Repair the independently proved REGIMM annulled-slot Count omission in "
            "src/boot/native_boot.cpp, in the opt-in original-OS reference profile only. "
            "The protected checker executes the existing accounting statements unchanged: "
            "all 28 oracle cases run, and only untaken BLTZL/BGEZL currently fail at "
            "16/128 iterations (130/1026 ticks versus 162/1282). Add the qualified "
            "REGIMM primary=1 rt=2/3 case to the existing skipped-delay-slot accounting, "
            "without double charging taken slots or changing the existing ERET exemption. "
            "Do not include ordinary REGIMM, branch-and-link variants, or COP1 likely: "
            "those are outside this micro's qualification. Update the nearby comment "
            "accurately. Preserve the accounting extraction anchors (previous_primary "
            "declaration and mmio.guest_count assignment). Only this native source file "
            "may change. No generated code, timer constants, VI adjustment, input/hash "
            "comparison changes, new profile flags, broad refactoring or other fixes. "
            "This is a corrected-Mupen profile repair, not a physical-N64 timing claim. "
            "There is no proof it fixes update 1909; independent replay will decide "
            "whether it regresses that baseline. Do not run the full build/replay yourself. "
            "Run the declared protected validation command and report its result. "
            "Source hashes and runtime hashes are different identities, not expected "
            "to equal each other; the pinned fresh build supplies their linkage.\n" +
            "Validation argv: " + json.dumps([real_python_executable(), str(checker),
                                            "src/boot/native_boot.cpp", str(trace)]) +
            "\nPinned evidence:\n" + "\n".join(str(path) for path in evidence)),
        "timeout_seconds": 600, "validation": [[real_python_executable(), str(checker),
                                                   "src/boot/native_boot.cpp", str(trace)]],
        "prerequisites": [case["diagnosis_id"], case["baseline_id"]],
        "retry_budget": 1, "allowed_paths": ["src/boot/native_boot.cpp"],
        "max_changed_files": 1,
        "evidence_files": [source_build.pin(path) for path in evidence],
        "candidate_build": recipe_from_build(build, case["baseline_id"], native, build_record),
    }
    validate_packet(implementation, repo)
    enqueue_packet(store, state, implementation, agent_binary)
    return job_id


def advance(store, repo, state, agent_binary, *, max_new_jobs=1):
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("repair advance budget must be 1..16")
    queued = []
    if (state / "PAUSED").exists():
        return queued
    for case in sorted((state / "repair-intake").glob("bc-*.json")):
        job = queue_case(store, repo, state, agent_binary, case)
        if job is None:
            from scripts.autonomy.candidate_review import (
                evidence_review_id, queue_evidence_review, review_id,
            )
            identity = hashlib.sha256(canonical_bytes(json.loads(case.read_text()))).hexdigest()[:12]
            review = review_id("bc-" + identity)
            states = {row["job_id"]: row["state"] for row in store.status_projection()["jobs"]}
            if states.get(review) == "passed" and evidence_review_id(review) not in states:
                job = queue_evidence_review(store, repo, state, agent_binary, review)
        if job:
            queued.append(job)
        if len(queued) == max_new_jobs:
            break
    return queued


def drive_case(repo, state, agent_binary, case_path, *, max_jobs=3):
    """Resume one finite repair/review/replay chain, never unrelated backlog."""
    from scripts.autonomy.candidate_review import queue_review, queue_evidence_review, review_id
    from scripts.autonomy.candidate_native_retest import queue_retest, retest_id
    from scripts.autonomy.supervisor import read_review, run_once
    if type(max_jobs) is not int or not 1 <= max_jobs <= 3:
        raise SupervisorError("repair drive budget must be 1..3")
    if (state / "PAUSED").exists():
        return {"state": "paused"}
    case = json.loads(case_path.read_text())
    implementation = "bc-" + hashlib.sha256(canonical_bytes(case)).hexdigest()[:12]
    for step in range(max_jobs + 1):
        with JobStore(state / "jobs.sqlite") as store:
            store.reclaim_expired()
            queue_case(store, repo, state, agent_binary, case_path)
            job_id = implementation
            stage = "implementation"
            job = store.job(job_id)
            known = {row["job_id"] for row in store.status_projection()["jobs"]}
            if job["state"] == "passed":
                review = review_id(implementation)
                if review not in known:
                    queue_review(store, repo, state, agent_binary, implementation)
                job_id, stage = review, "review"
                job = store.job(job_id)
                if job["state"] == "passed":
                    followup = queue_evidence_review(store, repo, state, agent_binary, review)
                    if followup:
                        review = followup
                        job_id = review
                        job = store.job(job_id)
                if job["state"] == "passed":
                    retest = retest_id(review)
                    if retest not in known:
                        next_id = queue_retest(store, repo, state, review)
                        if next_id is None:
                            _, result, sealed = _sealed_result(store, state, review, "packet:")
                            verdict = read_review(sealed.parent / "last-message.txt")
                            return {"state": "complete", "stage": stage, "job_id": job_id,
                                    "disposition": "review-" + verdict["verdict"],
                                    "candidate_only": True, "parity_verified": False}
                    job_id, stage = retest, "native-retest"
                    job = store.job(job_id)
                    if job["state"] == "passed":
                        _, result, _ = _sealed_result(store, state, job_id, "candidate-retest-packet:")
                        return {"state": "complete", "stage": stage, "job_id": job_id,
                                "disposition": result.get("candidate_disposition", "legacy-diagnostic"),
                                "raw_frontier": result["raw_frontier"],
                                "candidate_only": True, "parity_verified": False}
            if job["state"] != "queued" or step == max_jobs:
                return {"state": job["state"], "stage": stage, "job_id": job_id}
        outcome = run_once(repo, state, agent_binary, job_id=job_id)
        print(outcome, flush=True)
        if outcome == "paused":
            return {"state": "paused", "stage": stage, "job_id": job_id}
    raise AssertionError("bounded repair drive fell through")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnosis", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--oracle-trace", type=Path, required=True)
    parser.add_argument("--agent", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true", help="run only the newly queued implementation")
    mode.add_argument("--drive", action="store_true", help="resume this case through review and native retest")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    state = repo / "tools/private/autonomy"
    if (state / "PAUSED").exists():
        raise SupervisorError("repair intake is paused")
    case = register(repo, state, diagnosis_id=args.diagnosis, baseline_id=args.baseline,
                    oracle_report=args.oracle_report, oracle_trace=args.oracle_trace)
    with JobStore(state / "jobs.sqlite") as store:
        job = queue_case(store, repo, state, args.agent, case)
    print(json.dumps({"queued": job, "case": str(case)}), flush=True)
    if args.drive:
        print(json.dumps(drive_case(repo, state, args.agent, case)), flush=True)
    elif job and args.execute:
        from scripts.autonomy.supervisor import run_once
        print(run_once(repo, state, args.agent, job_id=job), flush=True)


if __name__ == "__main__":
    main()
