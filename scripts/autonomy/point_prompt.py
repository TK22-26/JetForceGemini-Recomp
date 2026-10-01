"""Lossless point-planner formatting and one contained pre-launch recovery.

This is not a model retry: only the exact prompt-limit preflight failure, with
no worktree, process receipt or model output, can get one replacement packet.
Old packets, ledger entries and full history facts remain immutable.
"""
import copy
import hashlib
import json
from pathlib import Path

from scripts.autonomy.supervisor import (
    MAX_PROMPT, SupervisorError, canonical_bytes, file_sha256, validate_packet,
)

SUFFIX = "-prompt-v1"
FAILURE = "prompt must be 1..20000 characters"
MARKERS = (
    "\nContract:\n",
    "\nSaved diagnosis (evidence):\n",
    "\nPrevious planner result:\n",
    "\nAdditional instruction evidence, decoded automatically from all retained focused snapshots on both sides:\n",
)
TABLE = "$point_rows"
NOTICE = ('Lossless JSON tables use {"$point_rows":{"columns":[keys],"rows":[values]}}; '
          'each row reconstructs an object by pairing its values with columns. '
          'No evidence fields, rows or qualification limits are omitted.\n')


def _json(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def tabulate(value):
    if isinstance(value, dict):
        if TABLE in value:
            raise SupervisorError("point evidence uses reserved table key")
        return {key: tabulate(item) for key, item in value.items()}
    if not isinstance(value, list):
        return value
    rows = [tabulate(item) for item in value]
    if len(value) >= 2 and all(isinstance(item, dict) for item in value):
        columns = list(value[0])
        if all(set(item) == set(columns) for item in value):
            table = {TABLE: {"columns": columns, "rows": [[row[key] for key in columns] for row in rows]}}
            if len(_json(table)) < len(_json(rows)):
                return table
    return rows


def untabulate(value):
    if isinstance(value, dict):
        if TABLE in value:
            body = value[TABLE]
            return [dict(zip(body["columns"], (untabulate(cell) for cell in row))) for row in body["rows"]]
        return {key: untabulate(item) for key, item in value.items()}
    if isinstance(value, list):
        return [untabulate(item) for item in value]
    return value


def parts(prompt):
    """Parse four known JSON payloads; never rewrite string values or prose."""
    result, position = [], 0
    for marker in MARKERS:
        start = prompt.find(marker, position)
        if start < 0:
            raise SupervisorError("point prompt lacks expected evidence section")
        start += len(marker)
        try:
            value, length = json.JSONDecoder().raw_decode(prompt[start:])
        except ValueError as error:
            raise SupervisorError("point prompt evidence is not JSON") from error
        result.append((start, start + length, value))
        position = start + length
    return result


def compact(prompt):
    parsed = parts(prompt)
    rendered = prompt
    for start, end, value in reversed(parsed):
        packed = tabulate(value)
        if untabulate(packed) != value:
            raise SupervisorError("point prompt compaction changed evidence")
        rendered = rendered[:start] + _json(packed) + rendered[end:]
    return NOTICE + rendered


def _pin(path):
    return {"path": str(path), "sha256": file_sha256(path)}


def failed_packet(store, repo, state, failed_id):
    """Verify a narrow historical preflight failure, not just its error text."""
    if failed_id.endswith(SUFFIX):
        raise SupervisorError("point prompt recovery cannot recover another recovery")
    job = store.job(failed_id)
    history = store.attempt_history(failed_id)
    if (job["state"] != "blocked" or job["attempts"] != 1 or
            job.get("sealed_artifact") is not None or job.get("sealed_sha256") is not None or
            len(history) != 1 or history[0]["number"] != 1 or
            history[0]["outcome"] != "blocked" or history[0]["detail"] != FAILURE or
            history[0].get("artifact") is not None or history[0].get("artifact_sha256") is not None):
        raise SupervisorError("point prompt predecessor is not an unused preflight failure")
    directory = state / "attempts" / failed_id / "0001"
    result_path = directory / "result.json"
    if (set(directory.iterdir()) != {result_path} or
            (state / "worktrees" / failed_id).exists()):
        raise SupervisorError("point prompt predecessor has possible worker activity")
    expected_failure = {"attempt": 1, "candidate_only": True, "complete": False,
                        "job_id": failed_id, "schema": 1, "stop_reason": FAILURE}
    if canonical_bytes(json.loads(result_path.read_text())) != canonical_bytes(expected_failure):
        raise SupervisorError("point prompt preflight failure receipt changed")
    packet_path = state / "packets" / (failed_id + ".json")
    packet = json.loads(packet_path.read_text())
    digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    spec = job["spec"]
    if (packet.get("job_id") != failed_id or packet.get("kind") != "plan-point" or
            not isinstance(packet.get("prompt"), str) or len(packet["prompt"]) <= MAX_PROMPT or
            spec["inputs"] != ["packet:" + digest] or
            spec["prerequisites"] != packet["prerequisites"] or packet["retry_budget"] != 0 or
            spec["pins"]["source_commit"] != packet["source_commit"] or
            any(spec["pins"][key + "_sha256"] != file_sha256(Path(path))
                for key, path in packet["pin_files"].items())):
        raise SupervisorError("point prompt predecessor packet/pins changed")
    # The oversized prompt is the sole allowed validation failure. All other
    # schema, authority, source and evidence checks still apply unchanged.
    validate_packet({**packet, "prompt": "preflight validation placeholder"}, repo)
    replacement = copy.deepcopy(packet)
    replacement.update(job_id=failed_id + SUFFIX, prompt=compact(packet["prompt"]))
    replacement["evidence_files"] += [_pin(packet_path), _pin(result_path)]
    validate_packet(replacement, repo)
    return packet, replacement


def validate_recovery(store, repo, state, packet):
    if not packet["job_id"].endswith(SUFFIX):
        return
    _, expected = failed_packet(store, repo, state, packet["job_id"][:-len(SUFFIX)])
    if canonical_bytes(packet) != canonical_bytes(expected):
        raise SupervisorError("point prompt recovery differs from lossless predecessor")
