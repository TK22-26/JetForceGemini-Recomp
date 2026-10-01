"""Unsupported point plan -> bounded interval plan -> reuse/capture -> feedback."""
import hashlib
import json
import time
from pathlib import Path

from scripts.autonomy import interval_plan, interval_observation, point_experiment, point_observation, instruction_context
from scripts.autonomy import state_word_experiment as words
from scripts.autonomy.candidate_native_retest import _sealed_result
from scripts.autonomy.job_store import JobSpec
from scripts.autonomy.supervisor import SupervisorError, canonical_bytes, file_sha256, read_packet, enqueue_packet, validate_packet, _write_json_atomic, bounded_command, real_python_executable

# v1 duplicated full known-count probes in the prompt and exceeded its budget
# before any model started. Keep that failed packet; use bounded context v2.
PLAN_PREFIX = "interval-plan-v2-"
OPERAND_SUFFIX = "-operands-v1"


def preferred_plan_id(states, parent_id):
    base = words.identity(PLAN_PREFIX, parent_id)
    return base + OPERAND_SUFFIX if base + OPERAND_SUFFIX in states else base


def facts_path(state, parent_id, *, operands=False):
    return state / "interval-facts" / (parent_id + (OPERAND_SUFFIX if operands else "") + ".json")


def facts_for(context, *, operands=False):
    counts = interval_observation.retained_counts(context["point_runtime"], context["window"])
    facts = {"schema": 1, "kind": "retained-interval-planner-facts",
            "point_facts": point_experiment.history_facts(context, context["point_runtime"]),
            "retained_probe": interval_observation.registered_probe(), "known_counts": counts,
            "runtime": context["point_runtime"]["binding"],
            "alignment_validated": False, "causal_fix_proved": False, "parity_verified": False}
    if operands:
        facts.update(schema=2, instruction_context=instruction_context.inventory(
            context["point_runtime"]["reference"]["capture_seal"].parent, context["window"], context["diagnosis"]))
    return facts


def contract(context, facts):
    return interval_plan.contract(context["window"], context["point_runtime"]["binding"]["sha256"],
        [item["plan"] for item in context["history"]],
        [{key: row[key] for key in ("probe", "selection")} for row in facts["known_counts"]])


def queue_plan(store, repo, state, agent, parent_id):
    job_id = words.identity(PLAN_PREFIX, parent_id)
    if (state / "PAUSED").exists() or job_id in {row["job_id"] for row in store.status_projection()["jobs"]}:
        return None
    context = point_experiment.plan_context(store, repo, state, parent_id)
    if context["plan"]["operation"] != "needs-instrumentation":
        return None
    if not _preferred_point(store, context, parent_id):
        return None
    return _queue_plan(store, repo, state, agent, parent_id, context, facts_for(context))


def _preferred_point(store, context, parent_id):
    known = {row["job_id"] for row in store.status_projection()["jobs"]}
    preferred = point_experiment.preferred_plan_id(known, context["entry_plan_id"])
    if preferred not in known:
        preferred = parent_id
    return parent_id == preferred  # Historical proposals must not fork a second lane.


def queue_refresh(store, repo, state, agent, context):
    """One source-backed successor to a fully validated unsupported base plan.

    The caller owns full plan_context validation. A failed/running successor
    is never retried; changed prose alone or exhausted measurement budgets
    cannot authorize a refresh.
    """
    if (state / "PAUSED").exists() or context["plan"]["operation"] != "needs-instrumentation":
        return None
    parent_id = context["point_plan_id"]
    base = words.identity(PLAN_PREFIX, parent_id)
    known = {row["job_id"] for row in store.status_projection()["jobs"]}
    if context["plan_id"] != base or base + OPERAND_SUFFIX in known:
        return None
    parent = context["point_context"]
    if not _preferred_point(store, parent, parent_id) or context["plan_packet"]["experiment_contract"]["round"] > interval_plan.MAX_ROUNDS:
        return None
    facts = facts_for(parent, operands=True)
    if not facts["instruction_context"]["sites"]:
        return None
    return _queue_plan(store, repo, state, agent, parent_id, parent, facts, refresh=context)


def _queue_plan(store, repo, state, agent, parent_id, context, facts, *, refresh=None):
    operands = refresh is not None
    job_id = words.identity(PLAN_PREFIX, parent_id) + (OPERAND_SUFFIX if operands else "")
    path = facts_path(state, parent_id, operands=operands)
    if path.exists() and path.read_bytes() != canonical_bytes(facts):
        raise SupervisorError("interval planner facts changed")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(path, facts)
    c = contract(context, facts)
    # Full immutable facts remain pinned. The prompt contains the relevant
    # compact fields, not raw register dumps or unqualified transcript excerpts.
    calibration = facts["point_facts"]["runtime_calibration"]
    summary = {"caller_candidates": facts["point_facts"]["candidates"],
               "prior_observations": [{"operation": row["operation"], "probe": row["probe"],
                   "qualification": row["qualification"], "input_prefix_match": row["input_prefix_match"],
                   "measurements": [{key: value for key, value in measurement.items() if key in (
                       "update", "native", "oracle", "equal", "address", "register", "pc")}
                       for measurement in row["measurements"]]} for row in facts["point_facts"]["prior_observations"]],
               "runtime_calibration": {"qualification": calibration["qualification"],
                   "measurements": {side: [{key: value for key, value in row.items() if key in (
                       "update", "queue_valid_at_entry", "counted_receives", "return_v0")}
                       for row in rows] for side, rows in calibration["measurements"].items()}},
               "retained_probe": facts["retained_probe"],
               "known_counts": [{"selection": row["selection"],
                   "counts_update_native_oracle": [[v["update"],v["native"],v["oracle"]] for v in row["observations"]]}
                   for row in facts["known_counts"]]}
    extra_prompt = ""
    if operands:
        summary["static_operand_sites"] = instruction_context.projection(facts["instruction_context"])
        summary["previous_unsupported_plan"] = refresh["plan"]
        extra_prompt = (
            "New static_operand_sites derive from matching instruction bytes in EVERY retained snapshot. "
            "They describe a LW feeding a zero-test branch after a direct call to a bounded leaf that preserves RA. "
            "conditional_raw_ra applies only if execution follows that normal path: it is NOT observed execution, "
            "retirement, caller equivalence or a permission to normalize RA. A new grounded branch PC may be captured "
            "with the existing primitive. You may choose a narrower falsifiable subtest (operand differs versus "
            "equal at a specified selected occurrence) without claiming to decide the entire diagnosis or prove "
            "completed queue/device causality. Choose an occurrence justified by retained evidence. Actual selected "
            "prefixes must still match raw PC/thread/SP/RA/input; otherwise the result is inconclusive. ")
    packet = {"schema": 1, "job_id": job_id, "kind": "plan-interval", "experiment_contract": c,
        "source_commit": context["baseline_packet"]["source_commit"], "pin_files": context["baseline_packet"]["pin_files"],
        "prompt": (
            "Choose ONE typed interval-state experiment or needs-instrumentation. No tools, investigation, commands, "
            "writes, fixes or parity claims. The new primitive observes ALL threads strictly between a qualified call's "
            "previous caller return and its NEXT entry. It is not inside the call. Use a direct JAL/NOP anchor from "
            "retained evidence; include entry_pc and call_pc+8 in <=16 pcs and running-thread word 0x800a9e90 in <=16 words. "
            "Select events at selection.pc whose GPR selection.register LOW 32 BITS equal selection.value_lo. "
            "Predict event-count (other value fields null), register (64 bits), or word (selected aligned RDRAM word); "
            "values require a 1-based occurrence. Choose a next-invocation update strictly greater than focus start. "
            "Counts include other threads but do not prove successful queue operations. Value comparison additionally "
            "requires equal selected-event prefixes of PC, running thread, SP, RAW RA and controller poll. Different "
            "overlay RAs are NOT silently translated; incompatible prefixes mean inconclusive. Entry/return anchors "
            "require unique calls, matching caller/thread/stack and input polls. No Count/timing-truth comparison. "
            "Known counts below are already computed from retained captures; requesting them again is rejected. "
            "A different update or renamed field is not new evidence. Registered captures are reused for any subset "
            "of their PCs/words. A genuinely new grounded PC/word triggers one bounded paired capture, which must "
            "preserve complete update traces, all focused RDRAM snapshots and input. Keep the same interpretation of "
            "completed updates versus invocations. Max three interval rounds. If a different primitive or unproved "
            "address/call mapping is required, use needs-instrumentation with null probe/selection/prediction. "
            "Prose fields <=600 characters. A local observation never authorizes a repair. " + extra_prompt +
            "Evidence below is a compact projection; full facts/pins are retained separately. "
            "Known counts all use retained_probe's entry/call boundaries.\nContract (known_counts tabulated below):\n"+
            json.dumps({key:value for key,value in c.items() if key != "known_counts"}, separators=(",", ":"))+
            "\nChecked retained evidence:\n"+json.dumps(summary, separators=(",", ":"))+
            "\nSaved diagnosis:\n"+json.dumps(context["diagnosis"], separators=(",", ":"))),
        "timeout_seconds": 180, "validation": [], "prerequisites": [parent_id, context["baseline_id"]],
        "retry_budget": 0, "allowed_paths": [], "max_changed_files": 0,
        "evidence_files": [words.pin(p) for p in (context["plan_seal"], context["plan_message"], context["diagnosis_message"],
                                                  context["baseline_seal"], path)] + [context["point_runtime"]["binding"]]}
    if operands:
        packet["prerequisites"].append(refresh["plan_id"])
        packet["evidence_files"].extend(words.pin(refresh[key]) for key in ("plan_seal", "plan_message"))
    validate_packet(packet, repo)
    enqueue_packet(store, state, packet, agent)
    return job_id


def _plan_envelope(store, repo, state, plan_id):
    job, result, seal = _sealed_result(store, state, plan_id, "packet:")
    packet = read_packet(state / "packets" / (plan_id + ".json"), repo)
    digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    message = seal.parent / "last-message.txt"
    operands = plan_id.endswith(OPERAND_SUFFIX)
    prerequisites = packet["prerequisites"]
    base = words.identity(PLAN_PREFIX, prerequisites[0]) if prerequisites else ""
    if (packet["kind"] != "plan-interval" or len(prerequisites) != (3 if operands else 2) or
            plan_id != base + (OPERAND_SUFFIX if operands else "") or
            (operands and prerequisites[2] != base) or
            job["spec"]["inputs"] != ["packet:" + digest] or job["spec"]["prerequisites"] != packet["prerequisites"] or
            result.get("packet_sha256") != digest or result.get("pins") != job["spec"]["pins"] or
            result.get("experiment_plan_sha256") != file_sha256(message) or
            result.get("experiment_schema_sha256") != file_sha256(interval_plan.SCHEMA_FILE)):
        raise SupervisorError("interval plan lineage changed")
    return packet, seal, message, operands


def _checked_plan(parent, state, plan_id, envelope):
    packet, seal, message, operands = envelope
    facts = facts_for(parent, operands=True) if operands else facts_for(parent)
    path = facts_path(state, parent["plan_id"], operands=operands)
    c = contract(parent, facts)
    if (parent["plan"]["operation"] != "needs-instrumentation" or packet["experiment_contract"] != c or
            packet["prerequisites"][0] != parent["plan_id"] or
            (operands and (not facts["instruction_context"]["sites"] or c["round"] > interval_plan.MAX_ROUNDS)) or
            packet["prerequisites"][1] != parent["baseline_id"] or words.pin(path) not in packet["evidence_files"] or
            parent["point_runtime"]["binding"] not in packet["evidence_files"] or path.read_bytes() != canonical_bytes(facts) or
            any(words.pin(parent[key]) not in packet["evidence_files"] for key in
                ("plan_seal", "plan_message", "diagnosis_message", "baseline_seal")) or
            any(packet[key] != parent["baseline_packet"][key] for key in ("source_commit", "pin_files"))):
        raise SupervisorError("interval plan differs from checked predecessor facts")
    return {**parent, "point_context": parent, "point_plan_id": parent["plan_id"], "plan_id": plan_id, "plan_seal": seal,
            "plan_message": message, "plan_packet": packet, "plan": interval_plan.read(message, c)}


def plan_context(store, repo, state, plan_id, *, chain=()):
    if plan_id in chain or len(chain) >= words.MAX_PLAN_CHAIN:
        raise SupervisorError("interval history is cyclic or over budget")
    envelope = _plan_envelope(store, repo, state, plan_id)
    packet, _, _, operands = envelope
    parent = point_experiment.plan_context(store, repo, state, packet["prerequisites"][0], chain=(*chain, plan_id))
    if operands:
        original_id = packet["prerequisites"][2]
        if original_id in chain:
            raise SupervisorError("interval history is cyclic or over budget")
        # Recompute both versions against the SAME freshly validated parent;
        # this avoids a duplicate recursive walk, not an evidence check.
        original = _checked_plan(parent, state, original_id, _plan_envelope(store, repo, state, original_id))
        if (original["plan"]["operation"] != "needs-instrumentation" or
                any(words.pin(original[key]) not in packet["evidence_files"] for key in ("plan_seal", "plan_message"))):
            raise SupervisorError("interval operand refresh lacks an unsupported predecessor")
    return _checked_plan(parent, state, plan_id, envelope)


def tool_sha():
    paths = [Path(__file__), Path(interval_plan.__file__), interval_plan.SCHEMA_FILE,
             Path(interval_observation.__file__), Path(interval_observation.interval.__file__),
             Path(point_observation.__file__), Path(point_experiment.__file__), Path(words.__file__),
             Path(instruction_context.__file__)]
    return hashlib.sha256(canonical_bytes({**{path.name: file_sha256(path) for path in paths},
                                          "point_dependency_closure": point_experiment.tool_sha()})).hexdigest()


def capture_context(store, repo, state, context, capture_id):
    if capture_id is not None:
        return point_experiment.capture_context(store, repo, state, context, capture_id)
    if not interval_observation.can_reuse(context["plan"]["probe"]):
        raise SupervisorError("registered capture lacks requested interval points/words")
    runtime = context["point_runtime"]
    return {"mode": "registered-calibration", "capture_seal": Path(runtime["record"]["calibration"]["path"]),
            "capture_result": {"input_prefix_match": runtime["calibration"]["input_prefix"]["first_input_mismatch"] is None}}


def queue_observation(store, repo, state, context, capture_id):
    capture = capture_context(store, repo, state, context, capture_id)
    reference = context["point_runtime"]["reference"]
    job_id = words.identity("interval-observe-", context["plan_id"])
    packet = {"schema": 1, "job_id": job_id, "plan_id": context["plan_id"], "capture_id": capture_id,
              "plan_result": words.pin(context["plan_seal"]), "capture_result": words.pin(capture["capture_seal"]),
              "reference_id": reference["capture_id"], "reference_result": words.pin(reference["capture_seal"]),
              "runtime": context["point_runtime"]["binding"]}
    path = state / "interval-packets" / (job_id + ".json")
    if path.exists() and path.read_bytes() != canonical_bytes(packet):
        raise SupervisorError("interval observation packet changed")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(path, packet)
    prerequisites = [context["plan_id"], reference["capture_id"]] + ([capture_id] if capture_id else [])
    store.enqueue(JobSpec(job_id, {**store.job(context["baseline_id"])["spec"]["pins"], "tool_sha256": tool_sha()},
                          ("interval-experiment:" + hashlib.sha256(canonical_bytes(packet)).hexdigest(),),
                          tuple(prerequisites), "analysis:interval-state", 1, "json_complete"))
    return job_id


def inputs(store, repo, state, job_id, spec, *, chain=()):
    packet = json.loads((state / "interval-packets" / (job_id + ".json")).read_text())
    fields = {"schema", "job_id", "plan_id", "capture_id", "plan_result", "capture_result", "reference_id", "reference_result", "runtime"}
    if (set(packet) != fields or type(packet["schema"]) is not int or packet["schema"] != 1 or packet["job_id"] != job_id or
            job_id != words.identity("interval-observe-", packet["plan_id"])):
        raise SupervisorError("interval observation identity changed")
    digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    prerequisites = [packet["plan_id"], packet["reference_id"]] + ([packet["capture_id"]] if packet["capture_id"] else [])
    if spec["inputs"] != ["interval-experiment:" + digest] or spec["prerequisites"] != prerequisites:
        raise SupervisorError("interval observation prerequisites changed")
    context = plan_context(store, repo, state, packet["plan_id"], chain=chain)
    if context["plan"]["operation"] != "interval-state":
        raise SupervisorError("interval observation requires a supported typed plan")
    capture = capture_context(store, repo, state, context, packet["capture_id"])
    runtime = context["point_runtime"]
    reference = runtime["reference"]
    baseline_pins = store.job(context["baseline_id"])["spec"]["pins"]
    if (any(spec["pins"][key] != value for key, value in baseline_pins.items() if key != "tool_sha256") or
            packet["plan_result"] != words.pin(context["plan_seal"]) or packet["capture_result"] != words.pin(capture["capture_seal"]) or
            packet["reference_id"] != reference["capture_id"] or packet["reference_result"] != words.pin(reference["capture_seal"]) or
            packet["runtime"] != runtime["binding"]):
        raise SupervisorError("interval observation evidence/source changed")
    reasons, instructions = [], None
    if packet["capture_id"] is None:
        raw = interval_observation.registered_rows(runtime, context["window"], context["plan"]["probe"])
    else:
        unchanged = all(capture["capture_result"][side + "_trace_sha256"] == reference["capture_result"][side + "_trace_sha256"]
                        for side in ("native", "oracle"))
        raw, _, reasons, instructions = point_observation.capture_evidence(capture["capture_seal"].parent,
            reference["capture_seal"].parent, context["plan"]["probe"], context["window"], traces_unchanged=unchanged)
    report = interval_observation.evaluate(raw, context["plan"], context["window"], reasons=reasons, instructions=instructions)
    # Recheck the complete plan/runtime/capture lineage after reading the data.
    after = plan_context(store, repo, state, packet["plan_id"], chain=chain)
    capture_context(store, repo, state, after, packet["capture_id"])
    report.update(complete=True, job_id=job_id, packet_sha256=digest, pins=spec["pins"],
                  capture_mode="registered-calibration" if packet["capture_id"] is None else "paired-capture",
                  **{key: packet[key] for key in ("plan_result", "capture_result", "reference_result", "runtime")})
    return report, {**context, "capture": capture, "reference": reference}


def checked_observation(store, repo, state, observation_id, *, chain=()):
    job, result, seal = _sealed_result(store, state, observation_id, "interval-experiment:")
    expected, context = inputs(store, repo, state, observation_id, job["spec"], chain=chain)
    if canonical_bytes(result) != canonical_bytes(expected):
        raise SupervisorError("sealed interval result contradicts its evidence")
    return {**context, "observation": result, "observation_id": observation_id, "observation_seal": seal}


def run_lease(store, lease, repo, state):
    job_id, token = lease["job_id"], lease["token"]
    directory = state / "attempts" / job_id / f"{lease['attempt']:04d}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "result.json"
    try:
        if lease["spec"]["pins"]["tool_sha256"] != tool_sha():
            raise SupervisorError("interval observation producer changed")
        store.start(job_id, token)
        command = [real_python_executable(), "-m", "scripts.autonomy.interval_experiment",
                   "--measure-job", job_id, "--repo", str(repo), "--state", str(state), "--output", str(path)]
        code, reason = bounded_command(command, repo, directory / "measurement.stdout", directory / "measurement.stderr",
                                  time.monotonic() + 600, lambda: store.heartbeat(job_id, token, ttl=120), state / "PAUSED",
                                  guard_record=directory / "measurement.guard.json")
        if code != 0 or reason is not None:
            raise SupervisorError(reason or "interval measurement process failed; see retained stderr")
        report = json.loads(path.read_text())
        if (report.get("complete") is not True or report.get("job_id") != job_id or report.get("pins") != lease["spec"]["pins"] or
                lease["spec"]["pins"]["tool_sha256"] != tool_sha()):
            raise SupervisorError("interval child result identity/producer changed")
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, path)
        store.pass_job(job_id, token)
        return f"{job_id}: interval observation sealed (qualified={report['qualification']['passed']})"
    except (OSError, ValueError) as error:
        _write_json_atomic(path, {"complete": False, "job_id": job_id, "stop_reason": str(error)[:300]})
        store.fail_job(job_id, token, str(error)[:300], blocked=True)
        return f"{job_id}: interval observation blocked ({error})"


def next_job(store, repo, state, agent, parent_id):
    if (state / "PAUSED").exists():
        return None
    states = {row["job_id"]: row["state"] for row in store.status_projection()["jobs"]}
    plan_id = preferred_plan_id(states, parent_id)
    if plan_id not in states:
        return queue_plan(store, repo, state, agent, parent_id)
    if states[plan_id] != "passed":
        return plan_id
    observation_id = words.identity("interval-observe-", plan_id)
    if observation_id in states:
        return observation_id
    context = plan_context(store, repo, state, plan_id)
    if context["plan"]["operation"] == "needs-instrumentation":
        return queue_refresh(store, repo, state, agent, context) or plan_id
    if interval_observation.can_reuse(context["plan"]["probe"]):
        return queue_observation(store, repo, state, context, None)
    point_observation.instruction_evidence(context["point_runtime"]["reference"]["capture_seal"].parent,
        context["window"], {key: context["plan"]["probe"][key] for key in ("entry_pc", "call_pc")})
    capture_id = point_experiment.ensure_capture(store, repo, state, context)
    if store.job(capture_id)["state"] != "passed":
        return capture_id
    return queue_observation(store, repo, state, context, capture_id)


def advance(store, repo, state, agent, *, max_new_jobs=1):
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("interval advance budget must be 1..16")
    if (state / "PAUSED").exists():
        return []
    rows = store.status_projection()["jobs"]
    known, queued = {row["job_id"] for row in rows}, []
    for row in reversed(rows):
        job = store.job(row["job_id"])
        if row["state"] != "passed" or not job["spec"]["inputs"][0].startswith("packet:"):
            continue
        packet = json.loads((state / "packets" / (row["job_id"] + ".json")).read_text())
        if packet.get("kind") != "plan-point":
            continue
        job_id = next_job(store, repo, state, agent, row["job_id"])
        if job_id and job_id not in known:
            queued.append(job_id)
            known.add(job_id)
            if len(queued) == max_new_jobs:
                break
    return queued


def main():
    import argparse
    from scripts.autonomy.job_store import JobStore
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure-job", required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo, state, output = args.repo.resolve(strict=True), args.state.resolve(strict=True), args.output.resolve()
    if not state.is_relative_to(repo / "tools/private") or not output.is_relative_to(state / "attempts" / args.measure_job):
        raise SupervisorError("interval measurement output escaped private attempt storage")
    if (state / "PAUSED").exists() or output.exists():
        raise SupervisorError("interval measurement paused or output already exists")
    with JobStore(state / "jobs.sqlite") as store:
        job = store.job(args.measure_job)
        if job["state"] != "running" or job["spec"]["pins"]["tool_sha256"] != tool_sha():
            raise SupervisorError("interval measurement requires the current running producer")
        report, _ = inputs(store, repo, state, args.measure_job, job["spec"])
    _write_json_atomic(output, report)


if __name__ == "__main__":
    main()
