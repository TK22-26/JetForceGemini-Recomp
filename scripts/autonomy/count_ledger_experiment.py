"""Qualified oracle Count-ledger supplement to an existing device observation.

Registration is an engineering intake, not permission to execute model-authored
commands. A separate bounded worker recomputes the parent and new evidence.
"""
import hashlib
import json
from pathlib import Path
import time

from scripts.autonomy import device_experiment as parent_lane, device_observation, source_build
from scripts.autonomy import state_word_experiment as words
from scripts.autonomy.job_store import JobSpec, JobStore
from scripts.autonomy.supervisor import (SupervisorError, ID_RE, canonical_bytes, file_sha256,
    _write_json_atomic, bounded_command, real_python_executable)
from scripts import phase9_oracle_count_ledger as ledger
from scripts.phase95_bridge import runtime_digest

PREFIX = "count-ledger-experiment:"


def registration_path(state, parent_id):
    if not isinstance(parent_id, str) or not ID_RE.fullmatch(parent_id):
        raise SupervisorError("Count ledger parent ID is invalid")
    return state / "count-ledger-runtimes" / (parent_id + ".json")


def tool_sha():
    root = Path(__file__).resolve().parents[2]
    names = ("scripts/autonomy/count_ledger_experiment.py", "scripts/phase9_oracle_count_ledger.py",
             "scripts/phase9_oracle_cpu_boundaries.py", "scripts/oracle_cpu_boundaries.c",
             "scripts/oracle_cpu_boundaries.h", "scripts/oracle_cpu_boundaries.patch")
    return hashlib.sha256(canonical_bytes({"files": {name: file_sha256(root / name) for name in names},
                                          "parent": parent_lane.tool_sha()})).hexdigest()


def check(store, repo, state, record, *, chain=()):
    fields = {"schema", "kind", "parent_id", "oracle", "control", "oracle_build", "update",
              "measurement_sha256", "supporting_files"}
    if (not isinstance(record, dict) or set(record) != fields or type(record["schema"]) is not int or
            record["schema"] != 1 or record["kind"] != "oracle-count-ledger-registration"):
        raise SupervisorError("Count ledger registration schema differs")
    registration_path(state, record["parent_id"])
    parent = parent_lane.checked_observation(store, repo, state, record["parent_id"], chain=chain)
    update = record["update"]
    if (type(update) is not int or not parent["window"][0] <= update <= parent["window"][1] or
            parent["plan"]["operation"] != "device-events" or
            parent["observation"]["qualification"]["passed"] is not True):
        raise SupervisorError("Count ledger needs a qualified device parent and bounded update")
    matches = [row for row in parent["observation"]["observations"] if row["update"] == update]
    if len(matches) != 1:
        raise SupervisorError("Count ledger parent interval is absent or ambiguous")
    selected = matches[0]["oracle"]
    first, last = selected["first_sequence_exclusive"], selected["last_sequence_exclusive"]
    directories = [parent_lane.private_directory(repo, record[key]) for key in ("oracle", "control")]
    prior = parent_lane.private_directory(repo, parent["device_registration"]["oracle"])
    build_path = source_build.pinned_file(repo, record["oracle_build"])
    support = [build_path.parent / name for name in ("build.guard.json", "build.stdout", "build.stderr", "emulator/config.ini")]
    if (not isinstance(record["supporting_files"], list) or
            [source_build.pinned_file(repo, item) for item in record["supporting_files"]] != support):
        raise SupervisorError("Count ledger build supporting receipts differ")
    build = parent_lane.oracle_build(repo, record["oracle_build"])
    for name in ("oracle_cpu_boundaries.c", "oracle_cpu_boundaries.h"):
        if file_sha256(repo / "scripts" / name) != file_sha256(build_path.parent / "mupen64plus-core/src/r4300" / name):
            raise SupervisorError("Count ledger built observer differs from its reader's producer")
    names = ["update-hashes.jsonl", "retrace-hashes.jsonl", "consumed-vi-hashes.jsonl",
             "point-probe.tsv", "device-events.tsv", "checkpoints.tsv"]
    names += [f"focus-update-{u}.rdram" for u in range(parent["window"][0], parent["window"][1] + 1)]
    paths = [base / name for base in (*directories, prior) for name in names + ["oracle-result.json"]]
    evidence = {str(path.resolve()): file_sha256(path) for path in paths}
    observed, control = directories
    if (control / "cpu-boundaries.tsv").exists():
        raise SupervisorError("Count ledger off-control contains an observer trace")
    for base in directories:
        device_observation.qualify_side(base, prior, parent["plan"]["probe"], parent["window"], "oracle")
        metadata = json.loads((base / "oracle-result.json").read_text())
        if (metadata.get("runtime_sha256") != build["runtime_sha256"] or
                metadata.get("mupen_cpu_core_override") != 1 or
                runtime_digest(base / "emulator") != build["runtime_sha256"] or
                (base == control and metadata.get("cpu_boundaries") is not None)):
            raise SupervisorError("Count ledger capture engine or off-control differs")
    for name in names:
        if len({evidence[str((base / name).resolve())] for base in (*directories, prior)}) != 1:
            raise SupervisorError("Count ledger instrumentation changed a complete control artifact")
    measured = ledger.measure(observed, first=first, last=last)
    if measured["ledger"]["update"] != update:
        raise SupervisorError("Count ledger capture changed the registered invocation")
    for key, boundary in (("start_context", measured["interval"]["start"]),
                          ("end_context", measured["interval"]["end"])):
        if (selected[key]["device_sequence"] != boundary["sequence"] or
                selected[key]["pc"] != boundary["pc"]):
            raise SupervisorError("Count ledger boundaries changed from the qualified parent")
    # Recheck backing data and producer after measurement; the existing parent
    # independently rechecks its complete lineage when consumed below.
    if evidence != {str(path.resolve()): file_sha256(path) for path in paths}:
        raise SupervisorError("Count ledger capture changed during measurement")
    parent_lane.oracle_build(repo, record["oracle_build"])
    for base in directories:
        if runtime_digest(base / "emulator") != build["runtime_sha256"]:
            raise SupervisorError("Count ledger runtime changed during measurement")
    for item in record["supporting_files"]:
        source_build.pinned_file(repo, item)
    report = {"kind": "jfg-qualified-oracle-count-ledger", "schema": 1, "focus_updates": parent["window"],
        "observations": [{"update": update, "oracle_count_ledger": measured["interval"],
                          "device_events_reconciled": len(measured["ledger"]["joined_devices"])}],
        "ledger_measurement": measured, "evidence": evidence,
        "qualification": {"passed": True, "reasons": [], "full_update_traces_unchanged": True,
                          "scope": "oracle-local-count-ledger-with-qualified-device-boundaries-not-cross-engine-clock"},
        "prediction_observed": None, "prediction_observation": None,
        "alignment_validated": False, "completed_queue_operations_proved": False,
        "clock_alignment_validated": False, "retirement_validated": False,
        "causal_fix_proved": False, "parity_verified": False}
    measurement = hashlib.sha256(canonical_bytes(report)).hexdigest()
    if record["measurement_sha256"] is not None and record["measurement_sha256"] != measurement:
        raise SupervisorError("Count ledger registered measurement changed")
    return report, parent


def register(store, repo, state, parent_id, *, oracle, control, oracle_build_path, update):
    if (state / "PAUSED").exists():
        raise SupervisorError("Count ledger registration is paused")
    path = registration_path(state, parent_id)
    record = {"schema": 1, "kind": "oracle-count-ledger-registration", "parent_id": parent_id,
        "oracle": str(oracle.resolve(strict=True)), "control": str(control.resolve(strict=True)),
        "oracle_build": words.pin(oracle_build_path), "update": update, "measurement_sha256": None,
        "supporting_files": [words.pin(oracle_build_path.parent / name) for name in
                             ("build.guard.json", "build.stdout", "build.stderr", "emulator/config.ini")]}
    report, _ = check(store, repo, state, record)
    record["measurement_sha256"] = hashlib.sha256(canonical_bytes(report)).hexdigest()
    if (state / "PAUSED").exists():
        raise SupervisorError("Count ledger paused during registration")
    if path.exists() and path.read_bytes() != canonical_bytes(record):
        raise SupervisorError("Count ledger registration is immutable")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(path, record)
    return words.pin(path)


def next_job(store, repo, state, agent, parent_id):
    path = registration_path(state, parent_id)
    if (state / "PAUSED").exists() or not path.is_file():
        return None
    binding = words.pin(path)
    job_id = words.identity("count-ledger-observe-", parent_id + ":" + binding["sha256"])
    if job_id in {row["job_id"] for row in store.status_projection()["jobs"]}:
        return job_id
    record = json.loads(path.read_text())
    if record["parent_id"] != parent_id or record.get("measurement_sha256") is None:
        raise SupervisorError("Count ledger registration is not qualified for this parent")
    parent_job, _, seal = words._sealed_result(store, state, parent_id, "device-experiment:")
    if words.pin(path) != binding:
        raise SupervisorError("Count ledger registration changed during queueing")
    if (state / "PAUSED").exists():
        return None
    packet = {"schema": 1, "job_id": job_id, "registration": binding, "parent_result": words.pin(seal)}
    packet_path = state / "count-ledger-packets" / (job_id + ".json")
    if packet_path.exists() and packet_path.read_bytes() != canonical_bytes(packet):
        raise SupervisorError("Count ledger packet is immutable")
    if not packet_path.exists():
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(packet_path, packet)
    pins = {**parent_job["spec"]["pins"], "tool_sha256": tool_sha()}
    store.enqueue(JobSpec(job_id, pins, (PREFIX + hashlib.sha256(canonical_bytes(packet)).hexdigest(),),
                          (parent_id,), "analysis:oracle-count-ledger", 0, "json_complete"))
    return job_id


def inputs(store, repo, state, job_id, spec, *, chain=()):
    if job_id in chain or len(chain) >= words.MAX_PLAN_CHAIN:
        raise SupervisorError("Count ledger history is cyclic or over budget")
    packet = json.loads((state / "count-ledger-packets" / (job_id + ".json")).read_text())
    if set(packet) != {"schema", "job_id", "registration", "parent_result"} or packet["schema"] != 1:
        raise SupervisorError("Count ledger packet schema differs")
    registration = source_build.pinned_file(repo, packet["registration"])
    record = json.loads(registration.read_text())
    expected = words.identity("count-ledger-observe-", record["parent_id"] + ":" + packet["registration"]["sha256"])
    packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    if (packet["job_id"] != job_id or job_id != expected or record["measurement_sha256"] is None or
            registration != registration_path(state, record["parent_id"]).resolve() or
            spec["inputs"] != [PREFIX + packet_sha] or spec["prerequisites"] != [record["parent_id"]]):
        raise SupervisorError("Count ledger identity or prerequisites changed")
    report, parent = check(store, repo, state, record, chain=(*chain, job_id))
    parent_pins = store.job(record["parent_id"])["spec"]["pins"]
    if ({k: v for k, v in spec["pins"].items() if k != "tool_sha256"} !=
            {k: v for k, v in parent_pins.items() if k != "tool_sha256"} or
            packet["parent_result"] != words.pin(parent["observation_seal"])):
        raise SupervisorError("Count ledger parent provenance changed")
    after = parent_lane.checked_observation(store, repo, state, record["parent_id"], chain=(*chain, job_id))
    if words.pin(after["observation_seal"]) != packet["parent_result"]:
        raise SupervisorError("Count ledger parent changed during measurement")
    source_build.pinned_file(repo, packet["registration"])
    for evidence in (report["evidence"], report["ledger_measurement"]["evidence"]):
        if any(file_sha256(Path(path)) != sha for path, sha in evidence.items()):
            raise SupervisorError("Count ledger evidence changed during lineage validation")
    parent_lane.oracle_build(repo, record["oracle_build"])
    for item in record["supporting_files"]:
        source_build.pinned_file(repo, item)
    report.update(complete=True, job_id=job_id, packet_sha256=packet_sha, pins=spec["pins"],
                  registration=packet["registration"], parent_result=packet["parent_result"])
    return report, {**parent, "history": [*parent["history"], parent], "plan_message": registration,
        "plan": {"operation": "oracle-count-ledger", "prediction": None,
                 "reason": "Registered local Count reconciliation, not aligned clocks or causal proof."}}


def checked_observation(store, repo, state, observation_id, *, chain=()):
    job, result, seal = words._sealed_result(store, state, observation_id, PREFIX)
    expected, context = inputs(store, repo, state, observation_id, job["spec"], chain=chain)
    if canonical_bytes(result) != canonical_bytes(expected):
        raise SupervisorError("Count ledger seal contradicts recomputed evidence")
    return {**context, "observation": result, "observation_id": observation_id, "observation_seal": seal}


def run_lease(store, lease, repo, state):
    job_id, token = lease["job_id"], lease["token"]
    directory = state / "attempts" / job_id / f"{lease['attempt']:04d}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "result.json"
    try:
        if lease["spec"]["pins"]["tool_sha256"] != tool_sha():
            raise SupervisorError("Count ledger producer changed")
        store.start(job_id, token)
        command = [real_python_executable(), "-m", "scripts.autonomy.count_ledger_experiment", "--measure-job", job_id,
                   "--repo", str(repo), "--state", str(state), "--output", str(path)]
        code, reason = bounded_command(command, repo, directory / "measurement.stdout", directory / "measurement.stderr",
            time.monotonic() + 1200, lambda: store.heartbeat(job_id, token, ttl=120), state / "PAUSED",
            guard_record=directory / "measurement.guard.json")
        if code != 0 or reason is not None:
            raise SupervisorError(reason or "Count ledger measurement failed; see retained stderr")
        report = json.loads(path.read_text())
        if (report.get("complete") is not True or report.get("job_id") != job_id or
                report.get("pins") != lease["spec"]["pins"] or tool_sha() != lease["spec"]["pins"]["tool_sha256"]):
            raise SupervisorError("Count ledger child identity or producer changed")
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, path)
        store.pass_job(job_id, token)
        return f"{job_id}: Count ledger observation sealed"
    except (OSError, ValueError) as error:
        _write_json_atomic(path, {"complete": False, "job_id": job_id, "stop_reason": str(error)[:300]})
        store.fail_job(job_id, token, str(error)[:300], blocked=True)
        return f"{job_id}: Count ledger observation blocked ({error})"


def advance(store, repo, state, agent, *, max_new_jobs=1):
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("Count ledger job budget must be 1..16")
    known = {row["job_id"] for row in store.status_projection()["jobs"]}
    queued = []
    for path in sorted((state / "count-ledger-runtimes").glob("*.json")):
        job_id = next_job(store, repo, state, agent, path.stem)
        if job_id and job_id not in known:
            queued.append(job_id)
            if len(queued) == max_new_jobs:
                break
    return queued


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure-job", required=True)
    for name in ("repo", "state", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    repo, state, output = args.repo.resolve(strict=True), args.state.resolve(strict=True), args.output.resolve()
    if (not ID_RE.fullmatch(args.measure_job) or not state.is_relative_to(repo / "tools/private") or
            not output.is_relative_to(state / "attempts" / args.measure_job) or output.exists() or (state / "PAUSED").exists()):
        raise SupervisorError("Count ledger output escaped private attempt, exists or is paused")
    with JobStore(state / "jobs.sqlite") as store:
        job = store.job(args.measure_job)
        if job["state"] != "running" or job["spec"]["pins"]["tool_sha256"] != tool_sha():
            raise SupervisorError("Count ledger measurement requires the current running producer")
        report, _ = inputs(store, repo, state, args.measure_job, job["spec"])
    _write_json_atomic(output, report)


if __name__ == "__main__":
    main()
