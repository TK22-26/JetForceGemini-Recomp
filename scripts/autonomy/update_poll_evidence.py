"""Derive a pinned, model-free poll/update alignment report from a sealed pair.

The report is diagnostic evidence, never a parity or implementation gate.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.autonomy.supervisor import SupervisorError, canonical_bytes, file_sha256
from scripts.phase9_update_alignment import analyze as analyze_updates
from scripts.phase9_update_poll_alignment import diagnose


def derive(state: Path, event_id: str, event: dict, repo: Path) -> tuple[Path, dict] | None:
    root = Path(event["pair_root"]).resolve(strict=True)
    native = root / "native" / "retrace-hashes.jsonl.updates.jsonl"
    oracle = root / "oracle" / "update-hashes.jsonl"
    alignment = analyze_updates(native, oracle)
    first = alignment.get("first_semantic_difference")
    if first is None:
        return None
    if (first.get("reason") != "state-difference" or
            type(first.get("update")) is not int or
            alignment.get("alignment_validated") is not False or
            alignment.get("parity_verified") is not False):
        raise SupervisorError("event pair has no supported update-clock frontier")
    diagnostic = diagnose(native, oracle, first["update"])
    report = {
        "kind": "jfg-autonomy-derived-update-poll-evidence", "schema": 1,
        "event_id": event_id,
        "event_pair_plan_sha256": file_sha256(root / "plan.json"),
        "event_pair_result_sha256": file_sha256(root / "pair-result.json"),
        "native_updates_sha256": file_sha256(native),
        "oracle_updates_sha256": file_sha256(oracle),
        "analyzer_sha256": file_sha256(
            Path(repo) / "scripts" / "phase9_update_poll_alignment.py"),
        "diagnostic": diagnostic,
        "alignment_validated": False, "parity_verified": False,
    }
    encoded = canonical_bytes(report)
    name = "update-poll-" + event_id + "-" + hashlib.sha256(
        encoded).hexdigest()[:16] + ".json"
    directory = Path(state) / "derived-evidence"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    if path.exists():
        if path.read_bytes() != encoded:
            raise SupervisorError("derived update-poll evidence changed")
    else:
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
    return path, report
