"""Registered device captures -> independently checked observation -> research.

Registration admits engineering instrumentation, never a model-authored command
or a gameplay repair. Each job remeasures the evidence; no success flag is trusted
in place of raw traces, source/runtime pins and the passed baseline lineage.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import time

from scripts.autonomy import device_observation, interval_experiment, source_build
from scripts.autonomy import state_word_experiment as words
from scripts.autonomy.job_store import JobSpec, JobStore
from scripts.autonomy.supervisor import (SupervisorError, canonical_bytes, file_sha256,
    _write_json_atomic, bounded_command, real_python_executable)
from scripts.phase95_bridge import runtime_digest


def registration_path(state, parent_id):
    return state / "device-runtimes" / (parent_id + ".json")


def tool_sha():
    root = Path(__file__).resolve().parents[2]
    names = ("scripts/autonomy/device_experiment.py", "scripts/autonomy/device_observation.py",
             "scripts/autonomy/source_build.py", "scripts/autonomy/source_snapshot.py",
             "scripts/autonomy/supervisor.py", "scripts/autonomy/job_store.py",
             "scripts/phase9_device_events.py", "scripts/phase95_poll_compare.py",
             "scripts/phase95_bridge.py", "scripts/build_phase9_route_replays.py",
             "scripts/oracle_device_events.c", "scripts/oracle_device_events.h",
             "scripts/oracle_device_events.patch", "include/jfg/boot/device_event_probe.h")
    return hashlib.sha256(canonical_bytes({
        **{name: file_sha256(root / name) for name in names},
        "interval_dependencies": interval_experiment.tool_sha()})).hexdigest()


def private_directory(repo, value):
    path = Path(value).resolve(strict=True)
    if not path.is_dir() or not path.is_relative_to(repo.resolve() / "tools/private"):
        raise SupervisorError("device evidence directory escaped private storage")
    return path


def oracle_build(repo, binding):
    """Check the retained guarded local build; not a hermetic build attestation."""
    path = source_build.pinned_file(repo, binding)
    report = json.loads(path.read_text())
    base = path.parent
    core, image = base / "mupen64plus-core", base / "emulator"
    if (report.get("schema") != 1 or report.get("complete") is not True or
            report.get("exit_code") != 0 or report.get("stop_reason") is not None or
            report.get("observation_only") is not True or
            not isinstance(report.get("source_files"), dict) or not report["source_files"] or
            json.loads((base / "build.guard.json").read_text()).get("state") != "finished"):
        raise SupervisorError("device oracle build is incomplete")
    for name, sha in report["source_files"].items():
        source = (core / name).resolve(strict=True)
        if not source.is_relative_to(core.resolve()) or file_sha256(source) != sha:
            raise SupervisorError("device oracle build source changed")
    command = report.get("command", [])
    if (len(command) < 2 or Path(command[0]).name.lower() != "msbuild.exe" or
            Path(command[1]).resolve() != (core / "projects/msvc/mupen64plus-core.vcxproj").resolve() or
            "/p:Configuration=Release" not in command or "/p:Platform=x64" not in command):
        raise SupervisorError("device oracle build command is not the retained core build")
    libraries = list(image.rglob("mupen64plus.dll"))
    if (len(libraries) != 1 or file_sha256(libraries[0]) != report.get("dll_sha256") or
            runtime_digest(image) != report.get("runtime_sha256")):
        raise SupervisorError("device oracle build runtime changed")
    return report


def check(store, repo, state, record, *, chain=()):
    fields = {"schema", "kind", "parent_id", "baseline_id", "reference_id", "source_build", "oracle_build",
              "native", "oracle", "probe", "selection", "occurrence", "measurement_sha256", "supporting_files"}
    if (not isinstance(record, dict) or set(record) != fields or type(record["schema"]) is not int or
            record["schema"] != 1 or record["kind"] != "diagnostic-device-registration"):
        raise SupervisorError("device registration schema changed")
    parent = interval_experiment.plan_context(store, repo, state, record["parent_id"], chain=chain)
    if parent["plan"]["operation"] != "needs-instrumentation" or record["baseline_id"] != parent["baseline_id"]:
        raise SupervisorError("device registration lacks a passed unsupported parent on this baseline")
    if any(item["plan"]["operation"] == "device-events" for item in parent["history"]):
        raise SupervisorError("device calibration cannot be reintroduced as new research evidence")
    reference = words.capture_context(store, repo, state, record["reference_id"], parent)
    if reference is None or any(key in reference["capture_packet"] for key in ("point_probe", "entry_probe")):
        raise SupervisorError("device reference must be the original unprobed capture")
    build_parent = Path(record["oracle_build"]["path"]).resolve().parent
    expected_support = [build_parent / name for name in
                        ("build.guard.json", "build.stdout", "build.stderr", "emulator/config.ini")]
    if (not isinstance(record["supporting_files"], list) or
            [source_build.pinned_file(repo, item) for item in record["supporting_files"]] != expected_support):
        raise SupervisorError("device oracle supporting build receipts changed")
    build_path = source_build.pinned_file(repo, record["source_build"])
    build = json.loads(build_path.read_text())
    build = source_build.validate(repo, record["source_build"], Path(build["executable"]))
    oracle = oracle_build(repo, record["oracle_build"])
    directories = [private_directory(repo, record[side]) for side in ("native", "oracle")]
    with tempfile.TemporaryDirectory(prefix="jfg-device-check-") as temporary:
        report = device_observation.measure(*directories, reference["capture_seal"].parent / "native",
            reference["capture_seal"].parent / "oracle", record["probe"], parent["window"],
            record["selection"], record["occurrence"], input_report_path=Path(temporary) / "input.json")
    native_result, oracle_result = [json.loads((path / f"{side}-result.json").read_text())
                                  for path, side in zip(directories, ("native", "oracle"))]
    if (native_result.get("executable_sha256") != build["executable_sha256"] or
            native_result.get("native_runtime_sha256") != build["runtime_sha256"] or
            oracle_result.get("runtime_sha256") != oracle["runtime_sha256"]):
        raise SupervisorError("device capture runtime differs from registered builds")
    # Exact isolated config equality with the reference is checked by measure.
    # The explicit core override must agree with the actual build image config.
    config = json.loads((Path(record["oracle_build"]["path"]).parent / "emulator/config.ini").read_text(encoding="utf-8-sig"))
    core_settings = config.get("CoreSyncSettings", {}).get("BizHawk.Emulation.Cores.Nintendo.N64.N64", {})
    if (core_settings.get("Core") != oracle_result.get("mupen_cpu_core_override") or
            runtime_digest(directories[1] / "emulator") != oracle["runtime_sha256"]):
        raise SupervisorError("device oracle interpreter changed from its configured core")
    measurement_sha = hashlib.sha256(canonical_bytes(report)).hexdigest()
    if record["measurement_sha256"] is not None and record["measurement_sha256"] != measurement_sha:
        raise SupervisorError("device registration measurement changed")
    return report, {**parent, "device_registration": record, "device_reference": reference}


def register(store, repo, state, parent_id, *, native, oracle, build, oracle_build_path,
             reference_id, baseline_id, probe, selection, occurrence):
    if (state / "PAUSED").exists():
        raise SupervisorError("device registration is paused")
    record = {"schema": 1, "kind": "diagnostic-device-registration", "parent_id": parent_id,
        "baseline_id": baseline_id, "reference_id": reference_id, "source_build": words.pin(build),
        "oracle_build": words.pin(oracle_build_path), "native": str(native.resolve(strict=True)),
        "oracle": str(oracle.resolve(strict=True)), "probe": probe, "selection": selection,
        "occurrence": occurrence, "measurement_sha256": None,
        "supporting_files": [words.pin(oracle_build_path.parent / name)
                             for name in ("build.guard.json", "build.stdout", "build.stderr", "emulator/config.ini")]}
    report, _ = check(store, repo, state, record)
    if (state / "PAUSED").exists():
        raise SupervisorError("device registration paused during validation")
    record["measurement_sha256"] = hashlib.sha256(canonical_bytes(report)).hexdigest()
    path = registration_path(state, parent_id)
    if path.exists() and path.read_bytes() != canonical_bytes(record):
        raise SupervisorError("device registration is immutable")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(path, record)
    return words.pin(path)


def next_job(store, repo, state, agent, parent_id):
    path = registration_path(state, parent_id)
    if (state / "PAUSED").exists() or not path.is_file():
        return None
    binding = words.pin(path)
    job_id = words.identity("device-observe-", parent_id + ":" + binding["sha256"])
    if job_id in {row["job_id"] for row in store.status_projection()["jobs"]}:
        return job_id  # Preserve running/failed/passed jobs; never relaunch.
    record = json.loads(path.read_text())
    if record["measurement_sha256"] is None or record["parent_id"] != parent_id:
        raise SupervisorError("device registration was not qualified for this parent")
    # Queueing is a routing operation, not evidence acceptance. The bounded
    # read-only worker below must recompute registration and complete ancestry
    # before AND after measurement. Do not duplicate that expensive graph walk
    # merely to schedule its verifier; authenticate the durable envelopes here.
    _, _, parent_seal = words._sealed_result(store, state, parent_id, "packet:")
    _, _, reference_seal = words._sealed_result(store, state, record["reference_id"], "update-packet:")
    baseline, _, _ = words._sealed_result(store, state, record["baseline_id"], "update-packet:")
    if words.pin(path) != binding:
        raise SupervisorError("device registration changed during queueing")
    if (state / "PAUSED").exists():
        return None
    packet = {"schema": 1, "job_id": job_id, "registration": binding,
              "parent_result": words.pin(parent_seal),
              "reference_result": words.pin(reference_seal)}
    packet_path = state / "device-packets" / (job_id + ".json")
    if packet_path.exists() and packet_path.read_bytes() != canonical_bytes(packet):
        raise SupervisorError("device observation packet is immutable")
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    if not packet_path.exists():
        _write_json_atomic(packet_path, packet)
    pins = {**baseline["spec"]["pins"], "tool_sha256": tool_sha()}
    store.enqueue(JobSpec(job_id, pins, ("device-experiment:" + hashlib.sha256(canonical_bytes(packet)).hexdigest(),),
        (parent_id, record["reference_id"]), "analysis:device-events", 0, "json_complete"))
    return job_id


def inputs(store, repo, state, job_id, spec, *, chain=()):
    if job_id in chain or len(chain) >= words.MAX_PLAN_CHAIN:
        raise SupervisorError("device observation history is cyclic or over budget")
    packet = json.loads((state / "device-packets" / (job_id + ".json")).read_text())
    if set(packet) != {"schema", "job_id", "registration", "parent_result", "reference_result"} or packet["schema"] != 1:
        raise SupervisorError("device observation packet fields differ")
    registration_file = source_build.pinned_file(repo, packet["registration"])
    record = json.loads(registration_file.read_text())
    expected_id = words.identity("device-observe-", record["parent_id"] + ":" + packet["registration"]["sha256"])
    digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    if (packet["job_id"] != job_id or job_id != expected_id or
            registration_file != registration_path(state, record["parent_id"]).resolve() or
            spec["inputs"] != ["device-experiment:" + digest] or
            spec["prerequisites"] != [record["parent_id"], record["reference_id"]] or record["measurement_sha256"] is None):
        raise SupervisorError("device observation identity or prerequisites changed")
    report, context = check(store, repo, state, record, chain=(*chain, job_id))
    baseline_pins = store.job(context["baseline_id"])["spec"]["pins"]
    if ({k: v for k, v in spec["pins"].items() if k != "tool_sha256"} !=
            {k: v for k, v in baseline_pins.items() if k != "tool_sha256"} or
            packet["parent_result"] != words.pin(context["plan_seal"]) or
            packet["reference_result"] != words.pin(context["device_reference"]["capture_seal"])):
        raise SupervisorError("device observation source/evidence lineage changed")
    # After measurement, independently revalidate the same complete parent lineage.
    after = interval_experiment.plan_context(store, repo, state, record["parent_id"], chain=(*chain, job_id))
    if (words.pin(after["plan_seal"]) != packet["parent_result"] or
            words.capture_context(store, repo, state, record["reference_id"], after) is None):
        raise SupervisorError("device parent/reference changed during measurement")
    source_build.pinned_file(repo, packet["registration"])
    build_path = source_build.pinned_file(repo, record["source_build"])
    source_build.validate(repo, record["source_build"], Path(json.loads(build_path.read_text())["executable"]))
    oracle_build(repo, record["oracle_build"])
    for item in record["supporting_files"]:
        source_build.pinned_file(repo, item)
    for side in device_observation.TRACES:
        for evidence_path, sha in report["evidence"][side]["files"].items():
            if file_sha256(Path(evidence_path)) != sha:
                raise SupervisorError("device capture changed after lineage validation")
    if any(file_sha256(Path(evidence_path)) != sha for evidence_path, sha in report["input_evidence"].items()):
        raise SupervisorError("device input changed after lineage validation")
    report.update(complete=True, job_id=job_id, packet_sha256=digest, pins=spec["pins"],
                  registration=packet["registration"], parent_result=packet["parent_result"], reference_result=packet["reference_result"])
    plan = {"operation": "device-events", "probe": record["probe"], "selection": record["selection"],
            "occurrence": record["occurrence"], "prediction": None,
            "reason": "Registered raw event observation; no model prediction or causal conclusion."}
    # Generic feedback consumers still get the original checked capture lineage;
    # the device evidence and both new runtime identities live in registration.
    return report, {**context, "plan": plan, "plan_message": registration_file,
                    "capture": context["device_reference"]}


def checked_observation(store, repo, state, observation_id, *, chain=()):
    job, result, seal = words._sealed_result(store, state, observation_id, "device-experiment:")
    expected, context = inputs(store, repo, state, observation_id, job["spec"], chain=chain)
    if canonical_bytes(result) != canonical_bytes(expected):
        raise SupervisorError("sealed device observation contradicts its raw evidence")
    return {**context, "observation": result, "observation_id": observation_id, "observation_seal": seal}


def run_lease(store, lease, repo, state):
    job_id, token = lease["job_id"], lease["token"]
    directory = state / "attempts" / job_id / f"{lease['attempt']:04d}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "result.json"
    try:
        if lease["spec"]["pins"]["tool_sha256"] != tool_sha():
            raise SupervisorError("device observation producer changed")
        store.start(job_id, token)
        command = [real_python_executable(), "-m", "scripts.autonomy.device_experiment", "--measure-job", job_id,
                   "--repo", str(repo), "--state", str(state), "--output", str(path)]
        code, reason = bounded_command(command, repo, directory / "measurement.stdout", directory / "measurement.stderr",
            time.monotonic() + 900, lambda: store.heartbeat(job_id, token, ttl=120), state / "PAUSED",
            guard_record=directory / "measurement.guard.json")
        if code != 0 or reason is not None:
            raise SupervisorError(reason or "device measurement process failed; see retained stderr")
        report = json.loads(path.read_text())
        if (report.get("complete") is not True or report.get("job_id") != job_id or
                report.get("pins") != lease["spec"]["pins"] or tool_sha() != lease["spec"]["pins"]["tool_sha256"]):
            raise SupervisorError("device child result identity/producer changed")
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, path)
        store.pass_job(job_id, token)
        return f"{job_id}: device observation sealed"
    except (OSError, ValueError) as error:
        _write_json_atomic(path, {"complete": False, "job_id": job_id, "stop_reason": str(error)[:300]})
        store.fail_job(job_id, token, str(error)[:300], blocked=True)
        return f"{job_id}: device observation blocked ({error})"


def advance(store, repo, state, agent, *, max_new_jobs=1):
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("device job budget must be 1..16")
    known = {row["job_id"] for row in store.status_projection()["jobs"]}
    queued = []
    for path in sorted((state / "device-runtimes").glob("*.json")):
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
    if (not state.is_relative_to(repo / "tools/private") or
            not output.is_relative_to(state / "attempts" / args.measure_job) or output.exists() or (state / "PAUSED").exists()):
        raise SupervisorError("device measurement output escaped private attempt, exists or is paused")
    with JobStore(state / "jobs.sqlite") as store:
        job = store.job(args.measure_job)
        if job["state"] != "running" or job["spec"]["pins"]["tool_sha256"] != tool_sha():
            raise SupervisorError("device measurement requires the current running producer")
        report, _ = inputs(store, repo, state, args.measure_job, job["spec"])
    _write_json_atomic(output, report)


if __name__ == "__main__":
    main()
