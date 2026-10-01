"""Unsupported word plan -> typed entry plan -> qualified paired register capture."""
import hashlib
import json
from pathlib import Path

from scripts.autonomy import entry_plan, entry_observation, state_word_experiment as words
from scripts.autonomy.job_store import JobSpec
from scripts.autonomy.candidate_native_retest import _sealed_result
from scripts.autonomy.supervisor import (
    SupervisorError, canonical_bytes, file_sha256, read_packet, enqueue_packet, _write_json_atomic,
)
from scripts.autonomy.update_job import queue_update


def queue_plan(store, repo, state, agent, parent_id):
    job_id = words.identity("entry-plan-", parent_id)
    if (state / "PAUSED").exists() or job_id in {row["job_id"] for row in store.status_projection()["jobs"]}:
        return None
    context = words.plan_context(store, repo, state, parent_id)
    if context["plan"]["operation"] != "needs-instrumentation":
        return None
    contract = entry_plan.contract(context["window"], [item["plan"] for item in context["history"]])
    packet = {
        "schema": 1, "job_id": job_id, "kind": "plan-entry", "experiment_contract": contract,
        "source_commit": context["baseline_packet"]["source_commit"],
        "pin_files": context["baseline_packet"]["pin_files"],
        "prompt": (
            "Translate the saved diagnosis into one typed entry-gpr experiment, or needs-instrumentation. "
            "Do not reinvestigate, use tools or execute anything. Select a KSEG0 function entry_pc "
            "and its direct JAL call_pc, grounded in the saved diagnosis. The executor qualifies "
            "JAL target, NOP delay slot and corresponding calls with RA=call_pc+8. It captures "
            "all 32 64-bit GPRs before the first callee instruction, <=1024 hits per side, "
            "at the pinned focus window. Choose one register index 0..31, invocation update and "
            "equal/different prediction. Native update_candidate and oracle completed_updates+1 "
            "name the invocation; raw clocks are retained and no state comparisons are shifted. "
            "Source/runtime, reference config, input and replay bounds are supervisor-owned. "
            "Both whole update traces must equal the prior focused capture, with matching input. "
            "Missing/ambiguous calls or changed traces are inconclusive. No writes, arbitrary "
            "commands, golden changes, game fixes or parity claims are allowed. If another "
            "primitive is needed, or the full-register probe was already measured, return "
            "needs-instrumentation with null probe/prediction. All prose fields <=600 characters.\n"
            "Pinned contract:\n" + json.dumps(contract) + "\nSaved diagnosis (evidence):\n" +
            json.dumps(context["diagnosis"]) + "\nPrevious planner result:\n" + json.dumps(context["plan"])),
        "timeout_seconds": 180, "validation": [], "prerequisites": [parent_id, context["baseline_id"]],
        "retry_budget": 0, "allowed_paths": [], "max_changed_files": 0,
        "evidence_files": [words.pin(path) for path in (context["plan_seal"], context["plan_message"],
                                                       context["diagnosis_message"], context["baseline_seal"])],
    }
    enqueue_packet(store, state, packet, agent)
    return job_id


def plan_context(store, repo, state, plan_id, *, chain=()):
    if plan_id in chain or len(chain) >= words.MAX_PLAN_CHAIN:
        raise SupervisorError("entry history is cyclic or over budget")
    job, result, seal = _sealed_result(store, state, plan_id, "packet:")
    packet = read_packet(state / "packets" / (plan_id + ".json"), repo)
    digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    message = seal.parent / "last-message.txt"
    if (packet["kind"] != "plan-entry" or len(packet["prerequisites"]) != 2 or
            job["spec"]["inputs"] != ["packet:" + digest] or job["spec"]["prerequisites"] != packet["prerequisites"] or
            result.get("packet_sha256") != digest or result.get("pins") != job["spec"]["pins"] or
            result.get("experiment_plan_sha256") != file_sha256(message) or
            result.get("experiment_schema_sha256") != file_sha256(entry_plan.SCHEMA_FILE)):
        raise SupervisorError("entry plan seal or lineage changed")
    parent = words.plan_context(store, repo, state, packet["prerequisites"][0], chain=(*chain, plan_id))
    expected = entry_plan.contract(parent["window"], [item["plan"] for item in parent["history"]])
    if (parent["plan"]["operation"] != "needs-instrumentation" or
            packet["experiment_contract"] != expected or packet["prerequisites"][1] != parent["baseline_id"] or
            packet["source_commit"] != parent["baseline_packet"]["source_commit"] or
            packet["pin_files"] != parent["baseline_packet"]["pin_files"]):
        raise SupervisorError("entry plan differs from its unsupported predecessor")
    plan = entry_plan.read(message, expected)
    return {**parent, "word_plan_id": parent["plan_id"], "word_plan_seal": parent["plan_seal"],
            "plan": plan, "plan_id": plan_id, "plan_seal": seal, "plan_message": message, "plan_packet": packet}


def ensure_capture(store, repo, state, context, *, reference=False):
    expected_probe = None if reference else context["plan"]["probe"]
    for row in reversed(store.status_projection()["jobs"]):
        if row["state"] == "passed" and store.job(row["job_id"])["spec"]["inputs"][0].startswith("update-packet:"):
            packet = json.loads((state / "update-packets" / (row["job_id"] + ".json")).read_text())
            if packet.get("entry_probe") != expected_probe:
                continue
            if words.capture_context(store, repo, state, row["job_id"], context) is not None:
                return row["job_id"]
    prefix = "entry-reference-" if reference else "entry-capture-"
    job_id = words.identity(prefix, context["plan_id"])
    if job_id not in {row["job_id"] for row in store.status_projection()["jobs"]}:
        first = context["first"]
        queue_update(store, repo, state, job_id=job_id, alignment_id=context["baseline_packet"]["alignment_id"],
                     alignment_result=context["plan_seal"], alignment_packet=context["baseline_packet"],
                     native_target=context["baseline_packet"]["native_target"], predecessor_id=context["plan_id"],
                     focus_pair={"native_before": first - 1, "oracle_before": first - 1,
                                 "native_after": first, "oracle_after": first}, entry_probe=expected_probe)
    return job_id


def capture_context(store, repo, state, context, capture_id, reference_id):
    capture = words.capture_context(store, repo, state, capture_id, context)
    reference = words.capture_context(store, repo, state, reference_id, context)
    if (capture is None or reference is None or
            capture["capture_packet"].get("entry_probe") != context["plan"]["probe"] or
            "entry_probe" in reference["capture_packet"] or
            capture["capture_packet"]["focus_updates"] != reference["capture_packet"]["focus_updates"]):
        raise SupervisorError("entry capture or reference changed target/window")
    expected = {f"{side}/entry-{kind}.tsv" for side in ("native", "oracle") for kind in ("args", "gpr")}
    digests = capture["capture_result"].get("entry_trace_sha256", {})
    if set(digests) != expected or any(file_sha256(capture["capture_seal"].parent / name) != digest
                                       for name, digest in digests.items()):
        raise SupervisorError("entry argument/register traces changed")
    return capture, reference


def measure(context, capture, reference):
    instructions = entry_observation.instruction_evidence(reference["capture_seal"].parent,
                                                         context["window"], context["plan"]["probe"])
    current = entry_observation.instruction_evidence(capture["capture_seal"].parent,
                                                    context["window"], context["plan"]["probe"])
    if current != instructions:
        raise SupervisorError("entry instruction bytes changed under instrumentation")
    unchanged = all(capture["capture_result"][side + "_trace_sha256"] ==
                    reference["capture_result"][side + "_trace_sha256"] for side in ("native", "oracle"))
    return entry_observation.measure(capture["capture_seal"].parent, context["plan"], context["window"],
                                     traces_unchanged=unchanged, instructions=instructions)


def tool_sha():
    files = [Path(__file__), Path(entry_plan.__file__), Path(entry_observation.__file__), entry_plan.SCHEMA_FILE,
             Path(words.__file__), Path(__file__).parents[1] / "compare_phase9_focus_rdram.py"]
    return hashlib.sha256(canonical_bytes({**{path.name: file_sha256(path) for path in files},
                                          "word_dependency_closure": words.tool_sha()})).hexdigest()


def queue_observation(store, repo, state, context, capture_id, reference_id):
    capture, reference = capture_context(store, repo, state, context, capture_id, reference_id)
    job_id = words.identity("entry-observe-", context["plan_id"])
    packet = {"schema": 1, "job_id": job_id, "plan_id": context["plan_id"],
              "capture_id": capture_id, "reference_id": reference_id,
              "plan_result": words.pin(context["plan_seal"]),
              "capture_result": words.pin(capture["capture_seal"]),
              "reference_result": words.pin(reference["capture_seal"])}
    path = state / "entry-packets" / (job_id + ".json")
    if path.exists() and path.read_bytes() != canonical_bytes(packet):
        raise SupervisorError("entry observation immutable packet changed")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(path, packet)
    pins = {**store.job(context["baseline_id"])["spec"]["pins"], "tool_sha256": tool_sha()}
    store.enqueue(JobSpec(job_id, pins, ("entry-experiment:" + hashlib.sha256(canonical_bytes(packet)).hexdigest(),),
                          (context["plan_id"], capture_id, reference_id), "analysis:entry-gpr", 1, "json_complete"))
    return job_id


def inputs(store, repo, state, job_id, spec, *, chain=()):
    packet = json.loads((state / "entry-packets" / (job_id + ".json")).read_text())
    fields = {"schema", "job_id", "plan_id", "capture_id", "reference_id", "plan_result", "capture_result", "reference_result"}
    if (set(packet) != fields or type(packet["schema"]) is not int or packet["schema"] != 1 or
            packet["job_id"] != job_id or job_id != words.identity("entry-observe-", packet["plan_id"])):
        raise SupervisorError("entry observation packet identity changed")
    digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    if (spec["inputs"] != ["entry-experiment:" + digest] or
            spec["prerequisites"] != [packet["plan_id"], packet["capture_id"], packet["reference_id"]]):
        raise SupervisorError("entry observation prerequisites changed")
    context = plan_context(store, repo, state, packet["plan_id"], chain=chain)
    capture, reference = capture_context(store, repo, state, context, packet["capture_id"], packet["reference_id"])
    expected_pins = {key: value for key, value in store.job(context["baseline_id"])["spec"]["pins"].items()
                     if key != "tool_sha256"}
    if ({key: value for key, value in spec["pins"].items() if key != "tool_sha256"} != expected_pins or
            packet["plan_result"] != words.pin(context["plan_seal"]) or
            packet["capture_result"] != words.pin(capture["capture_seal"]) or
            packet["reference_result"] != words.pin(reference["capture_seal"])):
        raise SupervisorError("entry observation pins changed")
    report = {**measure(context, capture, reference), "complete": True, "job_id": job_id,
              "packet_sha256": digest, "pins": spec["pins"],
              **{key: packet[key] for key in ("plan_result", "capture_result", "reference_result")}}
    capture_context(store, repo, state, context, packet["capture_id"], packet["reference_id"])
    return report, {**context, "capture": capture, "reference": reference}


def checked_observation(store, repo, state, observation_id, *, chain=()):
    job, result, seal = _sealed_result(store, state, observation_id, "entry-experiment:")
    expected, context = inputs(store, repo, state, observation_id, job["spec"], chain=chain)
    if canonical_bytes(result) != canonical_bytes(expected):
        raise SupervisorError("sealed entry experiment contradicts its evidence")
    return {**context, "observation": result, "observation_id": observation_id, "observation_seal": seal}


def run_lease(store, lease, repo, state):
    job_id, token = lease["job_id"], lease["token"]
    directory = state / "attempts" / job_id / f"{lease['attempt']:04d}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "result.json"
    try:
        if lease["spec"]["pins"]["tool_sha256"] != tool_sha():
            raise SupervisorError("entry observation producer changed")
        store.start(job_id, token)
        report, _ = inputs(store, repo, state, job_id, lease["spec"])
        _write_json_atomic(path, report)
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, path)
        store.pass_job(job_id, token)
        return f"{job_id}: entry observation sealed (qualified={report['qualification']['passed']})"
    except (OSError, ValueError) as error:
        _write_json_atomic(path, {"complete": False, "job_id": job_id, "stop_reason": str(error)[:300]})
        store.fail_job(job_id, token, str(error)[:300], blocked=True)
        return f"{job_id}: entry observation blocked ({error})"


def next_job(store, repo, state, agent, parent_id):
    if (state / "PAUSED").exists():
        return None
    states = {row["job_id"]: row["state"] for row in store.status_projection()["jobs"]}
    plan_id = words.identity("entry-plan-", parent_id)
    if plan_id not in states:
        return queue_plan(store, repo, state, agent, parent_id)
    if states[plan_id] != "passed":
        return plan_id
    observation_id = words.identity("entry-observe-", plan_id)
    if observation_id in states:
        return observation_id
    context = plan_context(store, repo, state, plan_id)
    if context["plan"]["operation"] == "needs-instrumentation":
        return plan_id
    reference_id = ensure_capture(store, repo, state, context, reference=True)
    if store.job(reference_id)["state"] != "passed":
        return reference_id
    reference = words.capture_context(store, repo, state, reference_id, context)
    entry_observation.instruction_evidence(reference["capture_seal"].parent, context["window"], context["plan"]["probe"])
    capture_id = ensure_capture(store, repo, state, context)
    if store.job(capture_id)["state"] != "passed":
        return capture_id
    return queue_observation(store, repo, state, context, capture_id, reference_id)


def advance(store, repo, state, agent, *, max_new_jobs=1):
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("entry experiment advance budget must be 1..16")
    if (state / "PAUSED").exists():
        return []
    rows = store.status_projection()["jobs"]
    known, queued = {row["job_id"] for row in rows}, []
    for row in reversed(rows):
        job = store.job(row["job_id"])
        if row["state"] != "passed" or not job["spec"]["inputs"][0].startswith("packet:"):
            continue
        packet = json.loads((state / "packets" / (row["job_id"] + ".json")).read_text())
        if packet.get("kind") != "plan-experiment":
            continue
        context = words.plan_context(store, repo, state, row["job_id"])
        if context["plan"]["operation"] != "needs-instrumentation":
            continue
        job_id = next_job(store, repo, state, agent, row["job_id"])
        if job_id and job_id not in known:
            queued.append(job_id)
            known.add(job_id)
            if len(queued) == max_new_jobs:
                break
    return queued
