"""Unsupported entry test -> typed instruction points -> measured feedback."""
import hashlib
import json
from pathlib import Path

from scripts.autonomy import point_plan, point_observation, point_runtime, point_anchors, point_prompt, entry_experiment, state_word_experiment as words
from scripts.autonomy.candidate_native_retest import _sealed_result
from scripts.autonomy.job_store import JobSpec
from scripts.autonomy.supervisor import SupervisorError, canonical_bytes, file_sha256, read_packet, enqueue_packet, _write_json_atomic, validate_packet
from scripts.autonomy.update_job import queue_update, point_trace_pins


def anchor_path(state, parent_id, *, history=False):
    return state/"point-anchors"/(parent_id+("-history-v2" if history else "")+".json")


def preferred_plan_id(states, parent_id):
    base = words.identity("point-plan-", parent_id)
    for suffix in ("-history-v2", "-anchors-v1", ""):
        if base + suffix + point_prompt.SUFFIX in states:
            return base + suffix + point_prompt.SUFFIX
        if base + suffix in states:
            return base + suffix
    return base


def queue_prompt_recovery(store, repo, state, agent, failed_id):
    if (state / "PAUSED").exists() or failed_id.endswith(point_prompt.SUFFIX):
        return None
    states = {row["job_id"]: row["state"] for row in store.status_projection()["jobs"]}
    successor = failed_id + point_prompt.SUFFIX
    if successor in states:
        return successor  # A queued/running/failed successor is never retried.
    original, replacement = point_prompt.failed_packet(store, repo, state, failed_id)
    # Only the unrefreshed, history-aware point packet is supported here.
    # Revalidate all parent measurements and the registered runtime before
    # accepting the saved prompt as the source of a first model invocation.
    parent_id = original["prerequisites"][0]
    if failed_id != words.identity("point-plan-", parent_id):
        raise SupervisorError("point prompt recovery requires the base planner")
    parent = entry_experiment.plan_context(store, repo, state, parent_id)
    runtime = point_runtime.load(store, repo, state, parent)
    if runtime is None:
        raise SupervisorError("point prompt recovery runtime is unavailable")
    contract = point_plan.contract(parent["window"], runtime["binding"]["sha256"], [item["plan"] for item in parent["history"]])
    facts = history_facts(parent, runtime)
    expected_payloads = [contract, parent["diagnosis"], parent["plan"], facts]
    expected_pins = [words.pin(path) for path in (parent["plan_seal"], parent["plan_message"],
        parent["diagnosis_message"], parent["baseline_seal"], anchor_path(state, parent_id, history=True))] + [runtime["binding"]]
    if (parent["plan"]["operation"] != "needs-instrumentation" or
            original["prerequisites"] != [parent_id, parent["baseline_id"]] or
            original["source_commit"] != parent["baseline_packet"]["source_commit"] or
            original["pin_files"] != parent["baseline_packet"]["pin_files"] or
            original["experiment_contract"] != contract or original["evidence_files"] != expected_pins or
            [value for _, _, value in point_prompt.parts(original["prompt"])] != expected_payloads or
            anchor_path(state, parent_id, history=True).read_bytes() != canonical_bytes(facts)):
        raise SupervisorError("point prompt recovery contradicts rechecked parent evidence")
    # Check the failure again after the expensive ancestry walk.
    point_prompt.validate_recovery(store, repo, state, replacement)
    enqueue_packet(store, state, replacement, agent)
    return successor


def has_anchors(context, state, *, history_only=False):
    paths = {anchor_path(state, context["entry_plan_id"], history=True)}
    if not history_only:
        paths.add(anchor_path(state, context["entry_plan_id"]))
    return any(Path(item["path"]) in paths for item in context["plan_packet"]["evidence_files"])


def history_facts(context, runtime):
    history = [{**item, "source": words.pin(item["observation_seal"]),
                "input_prefix_match": item.get("capture", {}).get("capture_result", {}).get("input_prefix_match")}
               for item in context["history"]]
    return point_anchors.history_inventory(runtime["reference"]["capture_seal"].parent,
        context["window"], context["diagnosis"], history, runtime["calibration"], runtime["record"]["calibration"])


def refresh_adds_evidence(context, state, facts):
    if context["plan"]["operation"] != "needs-instrumentation" or has_anchors(context,state,history_only=True):
        return False
    previous = {"candidates": []}
    if has_anchors(context,state):
        previous = json.loads(anchor_path(state,context["entry_plan_id"]).read_text())
    return point_anchors.adds_candidates(previous, facts)


def queue_plan(store, repo, state, agent, parent_id, *, refresh_from=None):
    context = entry_experiment.plan_context(store, repo, state, parent_id)
    if context["plan"]["operation"] != "needs-instrumentation" or (state / "PAUSED").exists():
        return None
    runtime = point_runtime.load(store, repo, state, context)
    if runtime is None:
        return None
    job_id = words.identity("point-plan-", parent_id)
    anchors = history_facts(context, runtime)
    if refresh_from is not None:
        old=plan_context(store,repo,state,refresh_from)
        if old["plan_id"] not in (job_id,job_id+"-anchors-v1") or old["entry_plan_id"] != parent_id:
            raise SupervisorError("point history refresh has a different predecessor")
        if not refresh_adds_evidence(old,state,anchors):
            return None
        job_id += "-history-v2"
    if job_id in {row["job_id"] for row in store.status_projection()["jobs"]}:
        return None
    contract = point_plan.contract(context["window"], runtime["binding"]["sha256"], [item["plan"] for item in context["history"]])
    facts_path=anchor_path(state,parent_id,history=True)
    if facts_path.exists() and facts_path.read_bytes() != canonical_bytes(anchors):
        raise SupervisorError("point anchor inventory changed")
    if not facts_path.exists():
        facts_path.parent.mkdir(parents=True,exist_ok=True)
        _write_json_atomic(facts_path,anchors)
    packet = {"schema":1, "job_id":job_id, "kind":"plan-point", "experiment_contract":contract,
        "source_commit":context["baseline_packet"]["source_commit"], "pin_files":context["baseline_packet"]["pin_files"],
        "prompt":(
            "Translate the saved diagnosis into one typed point-state experiment or needs-instrumentation. "
            "Do not reinvestigate, use tools, execute commands or propose a fix. A source-bound observation-only build "
            "is registered separately from the frozen baseline; every capture must reproduce both whole update traces "
            "and full focused RDRAM. Select a direct JAL/NOP producer anchor (entry_pc, call_pc); include its entry and "
            "call_pc+8 in pcs and the US running-thread word 0x800a9e90 in words. <=16 distinct PCs and <=16 aligned KSEG0 "
            "words, grounded in the diagnosis or checked retained evidence below. All 32 64-bit GPRs, selected words and opcodes are recorded before "
            "each instruction, <=4096 events/side, 300 seconds/side. Only the matching thread between the unique anchor "
            "entry/return is measured; all raw events survive. Native update_candidate and oracle completed_updates+1 "
            "identify the invocation; raw clocks stay separate. Prediction is event-count at pc (occurrence/register/address "
            "null), register at pc/1-based occurrence (address null), or word at pc/occurrence/address (register null). "
            "Choose an invocation in the focus window and relation equal/different. Values inside the call require equal "
            "observed hook prefixes; unique anchor entry/return values do not require identical internal event counts. "
            "Missing/ambiguous anchors, changed state/input or incompatible value prefixes are inconclusive, not proof of "
            "a bug. No Count comparison, dynamic memory dereferences, device reads/writes, input changes, game fixes, "
            "parity claims or arbitrary commands. Use needs-instrumentation with null probe/prediction when unsupported "
            "or already measured. All prose fields <=600 characters.\nContract:\n"+json.dumps(contract)+
            "\nSaved diagnosis (evidence):\n"+json.dumps(context["diagnosis"])+"\nPrevious planner result:\n"+json.dumps(context["plan"])+
            "\nAdditional instruction evidence, decoded automatically from all retained focused snapshots on both sides:\n"+json.dumps(anchors)+
            "\nPrior observations and runtime calibration were independently rechecked. Respect their qualification scope; "
            "do not recapture an already established count or queue value merely because it is absent from the latest diagnosis. "
            "Restored caller candidates do not extend the primitive: it still measures only the matching thread INSIDE "
            "one call, not other threads or the interval before its entry. Choose needs-instrumentation if that is required. "
            "\nThese direct JAL/NOP candidates are source-grounded addresses you may propose; choosing one does not invent execution qualification. "
            "The executor checks actual unique calls, thread/stack/RA and non-perturbation after capture. Do not claim those future checks already passed."),
        "timeout_seconds":180, "validation":[], "prerequisites":[parent_id,context["baseline_id"]], "retry_budget":0,
        "allowed_paths":[], "max_changed_files":0,
        "evidence_files":[words.pin(path) for path in (context["plan_seal"],context["plan_message"],context["diagnosis_message"],context["baseline_seal"],facts_path)]+[runtime["binding"]]}
    if refresh_from is not None:
        packet["prerequisites"].append(refresh_from)
        packet["evidence_files"].append(words.pin(old["plan_seal"]))
    packet["prompt"] = point_prompt.compact(packet["prompt"])
    validate_packet(packet, repo)  # Reject oversize before publishing/leasing.
    enqueue_packet(store, state, packet, agent)
    return job_id


def plan_context(store, repo, state, plan_id, *, chain=()):
    if plan_id in chain or len(chain) >= words.MAX_PLAN_CHAIN:
        raise SupervisorError("point experiment history is cyclic or over budget")
    job,result,seal = _sealed_result(store,state,plan_id,"packet:")
    packet = read_packet(state/"packets"/(plan_id+".json"),repo)
    point_prompt.validate_recovery(store, repo, state, packet)
    digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    message = seal.parent/"last-message.txt"
    if (packet["kind"] != "plan-point" or len(packet["prerequisites"]) not in (2,3) or
            job["spec"]["inputs"] != ["packet:"+digest] or job["spec"]["prerequisites"] != packet["prerequisites"] or
            result.get("packet_sha256") != digest or result.get("pins") != job["spec"]["pins"] or
            result.get("experiment_plan_sha256") != file_sha256(message) or
            result.get("experiment_schema_sha256") != file_sha256(point_plan.SCHEMA_FILE)):
        raise SupervisorError("point plan seal/lineage changed")
    base_id=words.identity("point-plan-",packet["prerequisites"][0])
    prior = None
    if len(packet["prerequisites"]) == 3:
        prior=plan_context(store,repo,state,packet["prerequisites"][2],chain=(*chain,plan_id))
        legacy = plan_id == base_id+"-anchors-v1" and prior["plan_id"] == base_id and not has_anchors(prior,state)
        history = plan_id == base_id+"-history-v2" and prior["plan_id"] in (base_id,base_id+"-anchors-v1") and not has_anchors(prior,state,history_only=True)
        if (not (legacy or history) or prior["plan"]["operation"] != "needs-instrumentation" or
                packet["prerequisites"][:2] != prior["plan_packet"]["prerequisites"][:2] or
                words.pin(prior["plan_seal"]) not in packet["evidence_files"]):
            raise SupervisorError("point evidence refresh ancestry changed")
    elif plan_id not in (base_id, base_id + point_prompt.SUFFIX):
        raise SupervisorError("point plan ID differs from predecessor")
    parent = entry_experiment.plan_context(store,repo,state,packet["prerequisites"][0],chain=(*chain,plan_id))
    runtime = point_runtime.load(store,repo,state,parent)
    if runtime is None:
        raise SupervisorError("point observation runtime is unavailable")
    expected = point_plan.contract(parent["window"],runtime["binding"]["sha256"],[item["plan"] for item in parent["history"]])
    if (parent["plan"]["operation"] != "needs-instrumentation" or packet["experiment_contract"] != expected or
            runtime["binding"] not in packet["evidence_files"] or packet["prerequisites"][1] != parent["baseline_id"] or
            packet["source_commit"] != parent["baseline_packet"]["source_commit"] or packet["pin_files"] != parent["baseline_packet"]["pin_files"]):
        raise SupervisorError("point plan differs from predecessor/runtime")
    facts_path = anchor_path(state,parent["plan_id"],history=True)
    if any(Path(item["path"]) == facts_path for item in packet["evidence_files"]):
        facts = history_facts(parent,runtime)
        if facts_path.read_bytes() != canonical_bytes(facts):
            raise SupervisorError("point history facts contradict their independently checked evidence")
        if prior is not None and not refresh_adds_evidence(prior,state,facts):
            raise SupervisorError("point history refresh adds no instruction candidates")
    elif plan_id == base_id+"-history-v2":
        raise SupervisorError("point history refresh lacks pinned history facts")
    return {**parent,"entry_plan_id":parent["plan_id"],"plan_id":plan_id,"plan_seal":seal,"plan_message":message,
            "plan_packet":packet,"plan":point_plan.read(message,expected),"point_runtime":runtime}


def capture_context(store, repo, state, context, capture_id):
    capture = words.capture_context(store,repo,state,capture_id,context,capture_baseline=context["point_runtime"]["capture_baseline"])
    if capture is None or capture["capture_packet"].get("point_probe") != context["plan"]["probe"]:
        raise SupervisorError("point capture changed source/build/probe")
    directory = capture["capture_seal"].parent
    traces = point_trace_pins(capture["capture_packet"],directory,
        json.loads((directory/"native/native-result.json").read_text()),json.loads((directory/"oracle/oracle-result.json").read_text()))
    if traces != capture["capture_result"].get("point_trace_sha256"):
        raise SupervisorError("point trace seals changed")
    return capture


def ensure_capture(store, repo, state, context):
    job_id = words.identity("point-capture-",context["plan_id"])
    if job_id not in {row["job_id"] for row in store.status_projection()["jobs"]}:
        first = context["first"]
        queue_update(store,repo,state,job_id=job_id,alignment_id=context["baseline_packet"]["alignment_id"],
            alignment_result=context["plan_seal"],alignment_packet=context["point_runtime"]["capture_baseline"],
            native_target=context["baseline_packet"]["native_target"],predecessor_id=context["plan_id"],
            focus_pair={"native_before":first-1,"oracle_before":first-1,"native_after":first,"oracle_after":first},
            point_probe=context["plan"]["probe"])
    return job_id


def tool_sha():
    files = [Path(__file__),Path(point_plan.__file__),point_plan.SCHEMA_FILE,Path(point_runtime.__file__),
             Path(point_observation.__file__),Path(point_anchors.__file__),Path(point_prompt.__file__),Path(words.__file__),Path(entry_experiment.__file__),
             Path(__file__).with_name("entry_observation.py"),
             Path(__file__).parents[1]/"compare_phase9_focus_rdram.py",
             Path(__file__).parents[1]/"compare_phase9_update_hashes.py",
             Path(__file__).parents[1]/"compare_phase9_retrace_hashes.py",
             Path(__file__).parents[1]/"phase9_point_probe.py",Path(__file__).parents[1]/"compare_phase9_point_pacing.py"]
    return hashlib.sha256(canonical_bytes({**{path.name:file_sha256(path) for path in files},
                                          "word_dependency_closure": words.tool_sha()})).hexdigest()


def queue_observation(store, repo, state, context, capture_id):
    capture = capture_context(store,repo,state,context,capture_id)
    reference = context["point_runtime"]["reference"]
    job_id = words.identity("point-observe-",context["plan_id"])
    packet = {"schema":1,"job_id":job_id,"plan_id":context["plan_id"],"capture_id":capture_id,
              "reference_id":reference["capture_id"],"plan_result":words.pin(context["plan_seal"]),
              "capture_result":words.pin(capture["capture_seal"]),"reference_result":words.pin(reference["capture_seal"]),
              "observation_runtime":context["point_runtime"]["binding"]}
    path = state/"point-packets"/(job_id+".json")
    if path.exists() and path.read_bytes() != canonical_bytes(packet):
        raise SupervisorError("point observation immutable packet changed")
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        _write_json_atomic(path,packet)
    pins = {**store.job(context["baseline_id"])["spec"]["pins"],"tool_sha256":tool_sha()}
    store.enqueue(JobSpec(job_id,pins,("point-experiment:"+hashlib.sha256(canonical_bytes(packet)).hexdigest(),),
                         (context["plan_id"],capture_id,reference["capture_id"]),"analysis:point-state",1,"json_complete"))
    return job_id


def inputs(store, repo, state, job_id, spec, *, chain=()):
    packet = json.loads((state/"point-packets"/(job_id+".json")).read_text())
    fields = {"schema","job_id","plan_id","capture_id","reference_id","plan_result","capture_result","reference_result","observation_runtime"}
    if (set(packet) != fields or type(packet["schema"]) is not int or packet["schema"] != 1 or packet["job_id"] != job_id or
            job_id != words.identity("point-observe-",packet["plan_id"])):
        raise SupervisorError("point observation identity changed")
    digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    if spec["inputs"] != ["point-experiment:"+digest] or spec["prerequisites"] != [packet["plan_id"],packet["capture_id"],packet["reference_id"]]:
        raise SupervisorError("point observation prerequisites changed")
    context = plan_context(store,repo,state,packet["plan_id"],chain=chain)
    capture = capture_context(store,repo,state,context,packet["capture_id"])
    reference = context["point_runtime"]["reference"]
    expected = {key:value for key,value in store.job(context["baseline_id"])["spec"]["pins"].items() if key != "tool_sha256"}
    if ({key:value for key,value in spec["pins"].items() if key != "tool_sha256"} != expected or
            packet["plan_result"] != words.pin(context["plan_seal"]) or packet["capture_result"] != words.pin(capture["capture_seal"]) or
            packet["reference_id"] != reference["capture_id"] or packet["reference_result"] != words.pin(reference["capture_seal"]) or
            packet["observation_runtime"] != context["point_runtime"]["binding"]):
        raise SupervisorError("point observation source/evidence pins changed")
    unchanged = all(capture["capture_result"][side+"_trace_sha256"] == reference["capture_result"][side+"_trace_sha256"] for side in ("native","oracle"))
    report = point_observation.measure(capture["capture_seal"].parent,reference["capture_seal"].parent,
                                      context["plan"],context["window"],traces_unchanged=unchanged)
    capture_context(store,repo,state,context,packet["capture_id"])
    # Recheck the plan/runtime after measurement, not only the generated trace.
    plan_context(store,repo,state,packet["plan_id"],chain=chain)
    report.update(complete=True,job_id=job_id,packet_sha256=digest,pins=spec["pins"],
                  **{key:packet[key] for key in ("plan_result","capture_result","reference_result","observation_runtime")})
    return report,{**context,"capture":capture,"reference":reference}


def checked_observation(store, repo, state, observation_id, *, chain=()):
    job,result,seal = _sealed_result(store,state,observation_id,"point-experiment:")
    expected,context = inputs(store,repo,state,observation_id,job["spec"],chain=chain)
    if canonical_bytes(result) != canonical_bytes(expected):
        raise SupervisorError("sealed point observation contradicts its evidence")
    return {**context,"observation":result,"observation_id":observation_id,"observation_seal":seal}


def run_lease(store, lease, repo, state):
    job_id,token = lease["job_id"],lease["token"]
    directory = state/"attempts"/job_id/f"{lease['attempt']:04d}"
    directory.mkdir(parents=True,exist_ok=True)
    path = directory/"result.json"
    try:
        if lease["spec"]["pins"]["tool_sha256"] != tool_sha():
            raise SupervisorError("point observation producer changed")
        store.start(job_id,token)
        report,_ = inputs(store,repo,state,job_id,lease["spec"])
        _write_json_atomic(path,report)
        store.verify(job_id,token)
        store.seal_artifact(job_id,token,path)
        store.pass_job(job_id,token)
        return f"{job_id}: point observation sealed (qualified={report['qualification']['passed']})"
    except (OSError,ValueError) as error:
        _write_json_atomic(path,{"complete":False,"job_id":job_id,"stop_reason":str(error)[:300]})
        store.fail_job(job_id,token,str(error)[:300],blocked=True)
        return f"{job_id}: point observation blocked ({error})"


def next_job(store, repo, state, agent, parent_id):
    if (state/"PAUSED").exists():
        return None
    states = {row["job_id"]:row["state"] for row in store.status_projection()["jobs"]}
    plan_id = preferred_plan_id(states, parent_id)
    if plan_id not in states:
        return queue_plan(store,repo,state,agent,parent_id)
    if states[plan_id] == "blocked" and not plan_id.endswith(point_prompt.SUFFIX):
        # Other failures remain terminal; the recovery validator rejects them.
        attempts = store.attempt_history(plan_id)
        if len(attempts) == 1 and attempts[0]["detail"] == point_prompt.FAILURE:
            return queue_prompt_recovery(store, repo, state, agent, plan_id) or plan_id
    if states[plan_id] != "passed":
        return plan_id
    observation_id = words.identity("point-observe-",plan_id)
    if observation_id in states:
        return observation_id
    context = plan_context(store,repo,state,plan_id)
    if context["plan"]["operation"] == "needs-instrumentation":
        if not has_anchors(context,state,history_only=True):
            return queue_plan(store,repo,state,agent,parent_id,refresh_from=plan_id) or plan_id
        return plan_id
    # Validate the direct JAL/NOP before spending time on a capture.
    point_observation.instruction_evidence(context["point_runtime"]["reference"]["capture_seal"].parent,
        context["window"],{key:context["plan"]["probe"][key] for key in ("entry_pc","call_pc")})
    capture_id = ensure_capture(store,repo,state,context)
    if store.job(capture_id)["state"] != "passed":
        return capture_id
    return queue_observation(store,repo,state,context,capture_id)


def advance(store, repo, state, agent, *, max_new_jobs=1):
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("point experiment advance budget must be 1..16")
    if (state/"PAUSED").exists():
        return []
    rows = store.status_projection()["jobs"]
    known,queued = {row["job_id"] for row in rows},[]
    for row in reversed(rows):
        job = store.job(row["job_id"])
        if row["state"] != "passed" or not job["spec"]["inputs"][0].startswith("packet:"):
            continue
        packet = json.loads((state/"packets"/(row["job_id"]+".json")).read_text())
        if packet.get("kind") != "plan-entry":
            continue
        job_id = next_job(store,repo,state,agent,row["job_id"])
        if job_id and job_id not in known:
            queued.append(job_id)
            known.add(job_id)
            if len(queued) == max_new_jobs:
                break
    return queued
