"""Resume a bounded measured-result research chain without draining the backlog.

This drives qualified experiment primitives, not arbitrary model-authored code.
A missing primitive is an explicit lane outcome, never a parity or goal pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.autonomy import experiment_feedback as feedback, state_word_experiment as experiment, entry_experiment
from scripts.autonomy import point_experiment, interval_experiment
from scripts.autonomy import device_experiment, count_ledger_experiment
from scripts.autonomy.job_store import JobStore
from scripts.autonomy.supervisor import SupervisorError, run_once, read_packet, canonical_bytes, file_sha256


def _routing_plan(store, repo, state, plan_id, module, kind):
    """Read a sealed routing hint, not an independently qualified experiment.

    The selected executor below still calls its full plan/context validator.
    This hint only avoids walking every earlier experiment lane to discover
    where the durable chain currently ends. It cannot authorize measurement,
    a repair, a retry, or acceptance of a result.
    """
    job, result, seal = experiment._sealed_result(store, state, plan_id, "packet:")
    packet = read_packet(state / "packets" / (plan_id + ".json"), repo)
    digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    message = seal.parent / "last-message.txt"
    schema = module.SCHEMA_FILE
    if (packet["kind"] != kind or job["spec"]["inputs"] != ["packet:" + digest] or
            job["spec"]["prerequisites"] != packet["prerequisites"] or
            result.get("packet_sha256") != digest or result.get("pins") != job["spec"]["pins"] or
            result.get("experiment_plan_sha256") != file_sha256(message) or
            result.get("experiment_schema_sha256") != file_sha256(schema)):
        raise SupervisorError("research routing hint has changed provenance")
    return module.read(message, packet["experiment_contract"]), packet


def _resume_tail(store, repo, state, agent, diagnosis_id):
    """Dispatch the deepest durable lane once; never cache its verification."""
    states = {row["job_id"]: row["state"] for row in store.status_projection()["jobs"]}
    word_id = experiment.identity("experiment-plan-", diagnosis_id)
    entry_id = experiment.identity("entry-plan-", word_id)
    point_id = point_experiment.preferred_plan_id(states, entry_id)
    interval_id = interval_experiment.preferred_plan_id(states, point_id)
    lanes = [
        (experiment, experiment.experiment_plan, "experiment", "plan-experiment", diagnosis_id, word_id, "word-experiment:"),
        (entry_experiment, entry_experiment.entry_plan, "entry-experiment", "plan-entry", word_id, entry_id, "entry-experiment:"),
        (point_experiment, point_experiment.point_plan, "point-experiment", "plan-point", entry_id, point_id, "point-experiment:"),
        (interval_experiment, interval_experiment.interval_plan, "interval-experiment", "plan-interval", point_id, interval_id, "interval-experiment:"),
    ]
    depth = None
    for index, lane in enumerate(lanes):
        if lane[5] not in states or (index and states[lanes[index - 1][5]] != "passed"):
            break
        depth = index
    if depth is None:
        return None  # Initial/legacy path, before any typed plan exists.
    if depth == 3 and state is not None:
        # A new registered observation is a separate evidence lane, not a retry
        # of an unsupported, failed or stale optional planner. Registration
        # itself requires a passed unsupported parent and new qualified data.
        base_interval = experiment.identity(interval_experiment.PLAN_PREFIX, point_id)
        for parent in dict.fromkeys((interval_id, base_interval)):
            if states.get(parent) != "passed" or not device_experiment.registration_path(state, parent).is_file():
                continue
            device_id = device_experiment.next_job(store, repo, state, agent, parent)
            if device_id is not None:
                job = store.job(device_id)
                if job["state"] == "passed":
                    return {"observation_id": device_id}
                return {"job_id": device_id, "stage": "device-observation", "state": job["state"], "parity_verified": False}
    executor, schema, stage, kind, parent_id, plan_id, observed_prefix = lanes[depth]
    if states[plan_id] != "passed":
        if depth == 2 and states[plan_id] == "blocked":
            successor = point_experiment.next_job(store, repo, state, agent, parent_id)
            if successor is not None and successor != plan_id:
                return {"job_id": successor, "stage": stage, "state": store.job(successor)["state"], "parity_verified": False}
        return {"job_id": plan_id, "stage": stage, "state": states[plan_id], "parity_verified": False}
    plan, packet = _routing_plan(store, repo, state, plan_id, schema, kind)
    if plan["operation"] == "needs-instrumentation":
        if depth == 3:
            # A terminal report, unlike a routing hint, needs the full validator.
            context = executor.plan_context(store, repo, state, plan_id)
            successor = executor.queue_refresh(store, repo, state, agent, context)
            if successor is not None:
                return {"job_id": successor, "stage": stage, "state": store.job(successor)["state"], "parity_verified": False}
            return {"job_id": plan_id, "stage": stage, "state": "needs-instrumentation",
                    "reason": context["plan"]["reason"],
                    "plan_result": experiment.pin(context["plan_seal"]), "parity_verified": False}
        if depth == 2 and not point_experiment.has_anchors(
                {"entry_plan_id": parent_id, "plan_packet": packet}, state, history_only=True):
            return None  # Preserve the qualified one-time historical anchor refresh.
        executor, _, stage, _, parent_id, _, observed_prefix = lanes[depth + 1]
    # next_job validates the complete passed parent/plan lineage before queueing
    # any new child. Pending workers and existing observations are never rerun.
    job_id = executor.next_job(store, repo, state, agent, parent_id)
    if job_id is None:
        return {"job_id": None, "state": "paused-or-unsupported", "parity_verified": False}
    job = store.job(job_id)
    if job["state"] == "passed":
        if not job["spec"]["inputs"][0].startswith(observed_prefix):
            raise SupervisorError("research tail stopped before a measured result")
        # The outer feedback transition independently recomputes this result.
        return {"observation_id": job_id}
    return {"job_id": job_id, "stage": stage, "state": job["state"], "parity_verified": False}


def next_stage(store, repo, state, agent, observation_id):
    if (state / "PAUSED").exists():
        return {"job_id": None, "state": "paused", "parity_verified": False}
    seen = set()
    for _ in range(experiment.MAX_RESEARCH_HISTORY):
        if observation_id in seen:
            raise SupervisorError("research chain repeats an observation")
        seen.add(observation_id)
        supplement = count_ledger_experiment.next_job(store, repo, state, agent, observation_id)
        if supplement is not None:
            job = store.job(supplement)
            if job["state"] == "passed":
                observation_id = supplement
                continue
            return {"job_id": supplement, "stage": "count-ledger-observation",
                    "state": job["state"], "parity_verified": False}
        feedback.queue_feedback(store, repo, state, agent, observation_id)
        diagnosis_id = feedback.feedback_id(observation_id)
        diagnosis_state = store.job(diagnosis_id)["state"]
        if diagnosis_state in ("failed", "blocked"):
            from scripts.autonomy import research_completion
            completed = research_completion.successor(store, repo, state, agent, observation_id)
            if completed is not None:
                diagnosis_id = completed
                diagnosis_state = store.job(diagnosis_id)["state"]
        if diagnosis_state != "passed":
            return {"job_id": diagnosis_id, "stage": "investigate", "state": diagnosis_state,
                    "parity_verified": False}
        tail = _resume_tail(store, repo, state, agent, diagnosis_id)
        if tail is not None:
            if "observation_id" in tail:
                observation_id = tail["observation_id"]
                continue
            return tail
        job_id = experiment.next_job(store, repo, state, agent, diagnosis_id)
        if job_id is None:
            return {"job_id": None, "state": "paused-or-unsupported", "parity_verified": False}
        job = store.job(job_id)
        if job["state"] != "passed":
            return {"job_id": job_id, "stage": "experiment", "state": job["state"],
                    "parity_verified": False}
        if job["spec"]["inputs"][0].startswith("packet:"):
            context = experiment.plan_context(store, repo, state, job_id)
            if context["plan"]["operation"] != "needs-instrumentation":
                raise SupervisorError("research chain stopped at an incomplete experiment")
            job_id = entry_experiment.next_job(store, repo, state, agent, job_id)
            if job_id is None:
                return {"job_id": None, "state": "paused-or-unsupported", "parity_verified": False}
            job = store.job(job_id)
            if job["state"] != "passed":
                return {"job_id": job_id, "stage": "entry-experiment", "state": job["state"], "parity_verified": False}
            if job["spec"]["inputs"][0].startswith("entry-experiment:"):
                observation_id = job_id
                continue
            context = entry_experiment.plan_context(store, repo, state, job_id)
            if context["plan"]["operation"] != "needs-instrumentation":
                raise SupervisorError("entry research stopped before measurement")
            point_id = point_experiment.next_job(store, repo, state, agent, job_id)
            if point_id is not None:
                job_id = point_id
                job = store.job(job_id)
                if job["state"] != "passed":
                    return {"job_id": job_id, "stage": "point-experiment", "state": job["state"], "parity_verified": False}
                if job["spec"]["inputs"][0].startswith("point-experiment:"):
                    observation_id = job_id
                    continue
                context = point_experiment.plan_context(store, repo, state, job_id)
                if context["plan"]["operation"] != "needs-instrumentation":
                    raise SupervisorError("point research stopped before measurement")
                interval_id = interval_experiment.next_job(store, repo, state, agent, job_id)
                if interval_id is not None:
                    job_id = interval_id
                    job = store.job(job_id)
                    if job["state"] != "passed":
                        return {"job_id": job_id, "stage": "interval-experiment", "state": job["state"], "parity_verified": False}
                    if job["spec"]["inputs"][0].startswith("interval-experiment:"):
                        observation_id = job_id
                        continue
                    context = interval_experiment.plan_context(store, repo, state, job_id)
                    if context["plan"]["operation"] != "needs-instrumentation":
                        raise SupervisorError("interval research stopped before measurement")
            return {"job_id": job_id, "stage": "experiment", "state": "needs-instrumentation",
                    "reason": context["plan"]["reason"],
                    "plan_result": experiment.pin(context["plan_seal"]), "parity_verified": False}
        if not job["spec"]["inputs"][0].startswith("word-experiment:"):
            raise SupervisorError("research chain has an unsupported result")
        observation_id = job_id
    raise SupervisorError("research chain exceeded its experiment round budget")


def drive(repo, state, agent, observation_id, *, max_jobs=1, execute=False, emit=None):
    if type(max_jobs) is not int or not 1 <= max_jobs <= 16 or type(execute) is not bool:
        raise SupervisorError("research cycle budget must be 1..16 named jobs")
    for dispatched in range(max_jobs + 1):
        with JobStore(state / "jobs.sqlite") as store:
            result = next_stage(store, repo, state, agent, observation_id)
        result["dispatched_jobs"] = dispatched
        if emit:
            emit(result)
        if not execute or result["state"] != "queued" or dispatched == max_jobs:
            return result
        # run_once rechecks pause, leases, ownership and the exact packet pins.
        message = run_once(repo, state, agent, job_id=result["job_id"])
        if emit:
            emit({"worker": message})
    raise AssertionError("bounded driver failed to return")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", required=True)
    parser.add_argument("--agent", required=True, type=Path)
    parser.add_argument("--max-jobs", type=int, default=4)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    drive(repo, repo / "tools/private/autonomy", args.agent, args.observation,
          max_jobs=args.max_jobs, execute=args.execute,
          emit=lambda value: print(json.dumps(value), flush=True))


if __name__ == "__main__":
    main()
