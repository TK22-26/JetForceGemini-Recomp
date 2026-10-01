"""Single-owner local supervisor loop with ledger audits and agent-attempt cap.

This is an opt-in process, not a startup service. It never bypasses a paused
queue or treats a sealed diagnostic/review result as parity or merge approval.
"""

from __future__ import annotations

from contextlib import contextmanager
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Callable, Iterator

from scripts.autonomy.job_store import ACTIVE, JobStore
from scripts.autonomy.supervisor import (
    SupervisorError, _inside, _write_json_atomic, file_sha256, run_once,
)


@contextmanager
def single_owner(state: Path) -> Iterator[None]:
    """Prevent two continuous loops from overrunning the daily agent cap."""
    state.mkdir(parents=True, exist_ok=True)
    with (state / "serve.lock").open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise SupervisorError("another continuous supervisor owns this state") from error
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise SupervisorError("another continuous supervisor owns this state") from error
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def agent_attempts_today(store: JobStore, *, now: float | None = None) -> int:
    """Count leases, including failed/expired attempts, by UTC day."""
    timestamp = time.time() if now is None else now
    today = datetime.fromtimestamp(timestamp, timezone.utc).date()
    count = 0
    for item in store.status_projection()["jobs"]:
        job_id = item["job_id"]
        inputs = store.job(job_id)["spec"]["inputs"]
        if inputs and inputs[0].startswith("packet:"):
            count += sum(datetime.fromtimestamp(attempt["started_at"],
                                                 timezone.utc).date() == today
                         for attempt in store.attempt_history(job_id))
    return count


def audit_state(store: JobStore, state: Path) -> dict:
    """Cross-check passed seals, attempt counts, and active resource locks."""
    jobs = store.status_projection()["jobs"]
    issues = []
    passed_verified = 0
    active_by_token = {}
    for item in jobs:
        job_id = item["job_id"]
        job = store.job(job_id)
        history = store.attempt_history(job_id)
        if job["attempts"] != len(history):
            issues.append({"job_id": job_id, "reason": "attempt-count-mismatch"})
        if job["state"] in ACTIVE:
            active_by_token[job["lease_token"]] = (job_id, job["resource"])
        if job["state"] != "passed":
            continue
        path = Path(job["sealed_artifact"]) if job["sealed_artifact"] else None
        try:
            seal_valid = (path is not None and path.is_file() and
                          _inside(path, state) and
                          file_sha256(path) == job["sealed_sha256"])
        except OSError:
            seal_valid = False
        if not seal_valid:
            issues.append({"job_id": job_id, "reason": "passed-seal-invalid"})
            continue
        if job["spec"]["completion_predicate"] == "json_complete":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                payload = None
            if not isinstance(payload, dict) or payload.get("complete") is not True:
                issues.append({"job_id": job_id, "reason": "passed-json-incomplete"})
                continue
        if sum(attempt["outcome"] == "passed" for attempt in history) != 1:
            issues.append({"job_id": job_id, "reason": "passed-attempt-count-invalid"})
            continue
        passed_verified += 1
    locks = store.connection.execute(
        "SELECT resource,job_id,token FROM resource_locks").fetchall()
    locked_tokens = set()
    for lock in locks:
        locked_tokens.add(lock["token"])
        if active_by_token.get(lock["token"]) != (lock["job_id"], lock["resource"]):
            issues.append({"job_id": lock["job_id"], "reason": "orphan-resource-lock"})
    for token, (job_id, _) in active_by_token.items():
        if token not in locked_tokens:
            issues.append({"job_id": job_id, "reason": "active-resource-lock-missing"})
    unresolved = [{"job_id": item["job_id"], "state": item["state"]}
                  for item in jobs if item["state"] in ("failed", "blocked")]
    return {"schema": 1, "kind": "jfg-autonomy-ledger-audit",
            "healthy": not issues, "job_count": len(jobs),
            "passed_verified": passed_verified, "issues": issues,
            "unresolved_jobs": unresolved,
            "counts": store.status_projection()["counts"]}


def write_audit(state: Path, report: dict) -> Path:
    directory = state / "audits"
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / (timestamp + ".json")
    _write_json_atomic(path, report)
    return path


def serve(repo: Path, state: Path, agent_binary: Path, *,
          poll_seconds: float = 15, max_cycles: int | None = None,
          max_agent_attempts_per_utc_day: int = 4,
          audit_seconds: float = 86_400,
          on_cycle: Callable[[dict], None] | None = None) -> list[str]:
    if (type(poll_seconds) not in (int, float) or
            not 0.1 <= poll_seconds <= 300 or
            max_cycles is not None and
            (type(max_cycles) is not int or not 1 <= max_cycles <= 100_000) or
            type(max_agent_attempts_per_utc_day) is not int or
            not 0 <= max_agent_attempts_per_utc_day <= 100 or
            type(audit_seconds) not in (int, float) or
            not 1 <= audit_seconds <= 86_400):
        raise SupervisorError("invalid continuous supervisor limits")
    if not _inside(state, repo / "tools" / "private"):
        raise SupervisorError("continuous state must stay under tools/private")
    from scripts.autonomy.scheduler import advance_jobs
    outcomes: deque[str] = deque(maxlen=32)
    with single_owner(state):
        last_audit = None
        cycles = 0
        while max_cycles is None or cycles < max_cycles:
            if last_audit is None or time.monotonic() - last_audit >= audit_seconds:
                with JobStore(state / "jobs.sqlite") as store:
                    report = audit_state(store, state)
                write_audit(state, report)
                last_audit = time.monotonic()
                if not report["healthy"]:
                    raise SupervisorError("ledger audit failed; see private audit report")
            if not (state / "PAUSED").exists():
                with JobStore(state / "jobs.sqlite") as store:
                    advance_jobs(store, repo, state, agent_binary)
            with JobStore(state / "jobs.sqlite") as store:
                agent_attempt_count = agent_attempts_today(store)
                allow_agent = (agent_attempt_count <
                               max_agent_attempts_per_utc_day)
            outcome = run_once(repo, state, agent_binary, allow_agent=allow_agent)
            outcomes.append(outcome)
            cycles += 1
            if on_cycle is not None:
                on_cycle({"cycle": cycles, "outcome": outcome,
                          "agent_attempts_today": agent_attempt_count,
                          "agent_cap": max_agent_attempts_per_utc_day})
            if outcome.startswith("progress-stopped:"):
                break  # Durable stop report; never poll/replan the same exhausted queue forever.
            if max_cycles is None or cycles < max_cycles:
                if outcome in ("idle", "paused"):
                    time.sleep(poll_seconds)
        return list(outcomes)
