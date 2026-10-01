"""Deterministic, bounded ledger transitions for the local autonomy loop.

This module queues read-only diagnoses and non-AI alignment captures. A raw
retrace mismatch is not a validated gameplay divergence and never creates an
implementation job.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.autonomy.job_store import JobStore
from scripts.autonomy import execution_contract as execution
from scripts.autonomy.candidate_review import queue_review, review_id
from scripts.autonomy.candidate_native_retest import queue_retest, retest_id
from scripts.autonomy.determinism_job import queue_determinism, determinism_id
from scripts.autonomy.frontier_cycle_job import queue_next as queue_frontier_next
from scripts.autonomy.poll_pair_job import (
    job_id_for as poll_pair_id, queue as queue_poll_pair,
    queue_from_controller_return,
    tool_sha256 as poll_pair_tool_sha256,
)
from scripts.autonomy.poll_lag_job import (
    job_id_for as poll_lag_id, queue as queue_poll_lag,
    tool_sha256 as poll_lag_tool_sha256,
    validate as validate_poll_lag_packet,
    _context as poll_pair_context,
)
from scripts.autonomy.event_pair_job import (
    _context as event_pair_context, derive_windows as derive_event_windows,
    event_capable, job_id_for as event_pair_id, queue as queue_event_pair,
    sealed_context as sealed_event_pair_context,
    tool_sha256 as event_pair_tool_sha256,
)
from scripts.autonomy.controller_return_job import (
    queue as queue_controller_return,
    sealed_context as sealed_controller_return_context,
)
from scripts.phase9_controller_return_pair import native_capable as controller_return_capable
from scripts.autonomy.input_focus_job import (
    _context as input_focus_context,
    job_id_for as input_focus_id, queue as queue_input_focus,
    sealed_context as sealed_input_focus_context,
    tool_sha256 as input_focus_tool_sha256,
)
from scripts.autonomy.update_poll_evidence import derive as derive_update_poll_evidence
from scripts.autonomy.alignment_job import queue_alignment, validate_alignment_packet
from scripts.autonomy.update_job import (
    queue_update, tool_sha256 as update_tool_sha256,
    validate as validate_update_packet,
)
from scripts.autonomy.vi_boundary_job import (
    queue_boundary, tool_sha256 as boundary_tool_sha256,
    validate as validate_boundary_packet,
)
from scripts.autonomy.supervisor import (
    PIN_FILES, SupervisorError, canonical_bytes,
    bounded_diagnosis_contract, diagnosis_schema_file,
    enqueue_packet, file_sha256, queue_diagnosis_report, read_diagnosis,
    read_packet, tool_identity_sha256, validate_comparison_packet,
    validate_packet, _git_ok,
)
from scripts.phase95_bridge import runtime_digest


POLL_PAIR_PLAN_TOOLS = (
    "scripts/phase9_poll_semantic_pair.py",
    "scripts/compare_phase9_poll_hashes.py",
    "scripts/phase95_native_replay.py",
    "scripts/phase9_point_probe.py",
    "scripts/phase95_oracle_replay.py",
    "scripts/phase9_oracle_instruction_effects.py",
    "scripts/phase9_bizhawk_oracle.lua",
)


def diagnosis_id(comparison_id: str) -> str:
    candidate = comparison_id + "-diagnosis"
    if len(candidate) <= 128:
        return candidate
    return "diag-" + hashlib.sha256(comparison_id.encode("ascii")).hexdigest()[:24]


def focus_diagnosis_id(lag_id: str, report_sha256: str,
                       clock_sha256: str | None = None) -> str:
    candidate = diagnosis_id(lag_id) + "-focus-" + report_sha256[:12]
    if clock_sha256 is not None:
        candidate += "-clock-" + clock_sha256[:12]
    if len(candidate) <= 128:
        return candidate
    return "diag-focus-" + hashlib.sha256(
        (lag_id + report_sha256 + (clock_sha256 or "")).encode(
            "ascii")).hexdigest()[:24]


def clock_diagnosis_id(lag_id: str, clock_sha256: str) -> str:
    candidate = diagnosis_id(lag_id) + "-clock-" + clock_sha256[:12]
    if len(candidate) <= 128:
        return candidate
    return "diag-clock-" + hashlib.sha256(
        (lag_id + clock_sha256).encode("ascii")).hexdigest()[:24]


def alignment_id(diagnosis_job_id: str) -> str:
    candidate = diagnosis_job_id + "-alignment"
    if len(candidate) <= 128:
        return candidate
    return "align-" + hashlib.sha256(diagnosis_job_id.encode("ascii")).hexdigest()[:24]


def update_id(alignment_job_id: str) -> str:
    candidate = alignment_job_id + "-updates"
    if len(candidate) <= 128:
        return candidate
    return "updates-" + hashlib.sha256(alignment_job_id.encode("ascii")).hexdigest()[:24]


def extended_update_id(update_job_id: str, target: int) -> str:
    candidate = f"{update_job_id}-to-{target}"
    if len(candidate) <= 128:
        return candidate
    return "updates-" + hashlib.sha256(candidate.encode("ascii")).hexdigest()[:24]


def rebased_update_id(update_job_id: str, current_identity: str) -> str:
    digest = hashlib.sha256((update_job_id + ":" + current_identity).encode(
        "ascii")).hexdigest()[:24]
    return "updates-rebase-" + digest


def update_diagnosis_id(update_job_id: str) -> str:
    candidate = update_job_id + "-diagnosis"
    if len(candidate) <= 128:
        return candidate
    return "updates-diag-" + hashlib.sha256(update_job_id.encode(
        "ascii")).hexdigest()[:24]


def focused_update_id(update_job_id: str) -> str:
    candidate = update_job_id + "-focus"
    if len(candidate) <= 128:
        return candidate
    return "updates-focus-" + hashlib.sha256(update_job_id.encode(
        "ascii")).hexdigest()[:24]


def focus_pair_for_later_mismatch(later: dict,
                                  prior_pair: dict | None = None) -> dict | None:
    """Recapture a moved frontier, but never spawn the same focus repeatedly."""
    if (later.get("reason") != "semantic-mismatch" or
            any(type(later.get(key)) is not int or later[key] < 2 for key in
                ("native_update", "oracle_update"))):
        return None
    pair = {"native_before": later["native_update"] - 1,
            "oracle_before": later["oracle_update"] - 1,
            "native_after": later["native_update"],
            "oracle_after": later["oracle_update"]}
    if pair == prior_pair or max(pair.values()) - min(pair.values()) >= 16:
        return None
    return pair


def vi_boundary_id(focus_job_id: str, tool_identity: str) -> str:
    digest = hashlib.sha256((focus_job_id + ":" + tool_identity).encode(
        "ascii")).hexdigest()[:24]
    return "vi-boundary-" + digest


def vi_boundary_diagnosis_id(boundary_job_id: str,
                             evidence_sha256: str) -> str:
    candidate = boundary_job_id + "-diagnosis-v2-" + evidence_sha256[:12]
    if len(candidate) <= 128:
        return candidate
    return "vi-diag-" + hashlib.sha256(candidate.encode(
        "ascii")).hexdigest()[:24]


def vi_boundary_diagnosis_facts(vi: dict, focus: dict,
                                transition: dict) -> dict:
    """Use measured boundary evidence, never a prior job's cadence narrative."""
    if (vi.get("kind") != "jfg-phase9-vi-boundary-comparison" or
            focus.get("kind") != "jfg-phase9-focus-rdram-comparison" or
            transition.get("kind") != "jfg-phase9-rdram-transition-comparison" or
            not isinstance(vi.get("focused_update_pair"), dict) or
            set(vi["focused_update_pair"]) != {
                "native_before", "native_after", "oracle_before", "oracle_after"} or
            not isinstance(vi.get("input_sha256"), str) or
            len(vi["input_sha256"]) != 64 or
            vi.get("focused_update_pair") !=
            transition.get("focused_update_pair") or
            any(report.get("alignment_validated") is not False or
                report.get("parity_verified") is not False
                for report in (vi, focus, transition)) or
            len({report.get("input_sha256") for report in
                 (vi, focus, transition)}) != 1):
        raise SupervisorError("VI diagnosis reports have inconsistent provenance")
    facts = {"focused_update_pair": vi["focused_update_pair"],
             "hook_equivalence": vi.get("hook_equivalence"),
             "alignment_validated": False,
             "parity_verified": False}
    for name in ("lead_in", "onset"):
        interval = vi.get(name)
        if (not isinstance(interval, dict) or
                any(type(interval.get(key)) is not int or interval[key] < 0
                    for key in ("native_consumptions", "oracle_consumptions"))):
            raise SupervisorError("VI diagnosis interval count is invalid")
        mismatch = interval.get("first_relative_mismatch")
        if mismatch is not None and (not isinstance(mismatch, dict) or
                                      type(mismatch.get("relative_consumption")) is not int):
            raise SupervisorError("VI diagnosis mismatch is invalid")
        facts[name] = {
            "native_consumptions": interval["native_consumptions"],
            "oracle_consumptions": interval["oracle_consumptions"],
            "first_relative_mismatch": mismatch,
        }
    for name in ("before", "after"):
        point = focus.get(name)
        if (not isinstance(point, dict) or
                type(point.get("semantic_state_match")) is not bool or
                not isinstance(point.get("actor_byte_differences"), list) or
                point.get("native_update") !=
                    vi["focused_update_pair"]["native_" + name] or
                point.get("oracle_update") !=
                    vi["focused_update_pair"]["oracle_" + name]):
            raise SupervisorError("VI diagnosis focus summary is invalid")
        facts[name] = {
            "semantic_state_match": point["semantic_state_match"],
            "actor_difference_count": len(point["actor_byte_differences"]),
        }
    inputs = focus.get("controller_inputs_between")
    changed = transition.get("transition")
    if (not isinstance(inputs, dict) or type(inputs.get("same_values")) is not bool or
            not isinstance(changed, dict) or
            any(type(changed.get(key)) is not int or changed[key] < 0 for key in
                ("new_actor_bytes", "new_non_actor_bytes"))):
        raise SupervisorError("VI diagnosis input or transition summary is invalid")
    facts["controller_values_match"] = inputs["same_values"]
    facts["new_actor_bytes"] = changed["new_actor_bytes"]
    facts["new_non_actor_bytes"] = changed["new_non_actor_bytes"]
    actor_words = transition.get("actor_word_changes")
    if actor_words is not None:
        if (not isinstance(actor_words, dict) or
                actor_words.get("scope") !=
                    "stable-actor-slots-raw-words-diagnostic-only" or
                type(actor_words.get("total_newly_divergent_words")) is not int or
                actor_words["total_newly_divergent_words"] < 0 or
                not isinstance(actor_words.get("first_newly_divergent_words"), list) or
                len(actor_words["first_newly_divergent_words"]) > 32 or
                len(actor_words["first_newly_divergent_words"]) >
                    actor_words["total_newly_divergent_words"] or
                any(not isinstance(row, dict) or
                    type(row.get("index")) is not int or row["index"] < 0 or
                    not isinstance(row.get("word_offset"), str) or
                    len(row["word_offset"]) != 5 or
                    not row["word_offset"].startswith("0x")
                    for row in actor_words["first_newly_divergent_words"])):
            raise SupervisorError("VI diagnosis actor-word summary is invalid")
        facts["new_actor_word_count"] = actor_words[
            "total_newly_divergent_words"]
        facts["first_actor_word_offsets"] = [
            {"index": row["index"], "word_offset": row["word_offset"]}
            for row in actor_words["first_newly_divergent_words"]]
    return facts


def diagnostic_suffix_allows_extension(result: dict, alignment: dict) -> bool:
    """Permit more *diagnostic capture*, never promote a resync to parity."""
    first = result.get("first_divergence") or {}
    anchor = alignment.get("same_poll_anchor")
    later = alignment.get("first_later_mismatch")
    native_ended = (alignment.get("native_suffix_exhausted") is True and
                    later is None)
    oracle_ended = (alignment.get("native_suffix_exhausted") is False and
                    isinstance(later, dict) and
                    later.get("reason") == "oracle-stream-ended" and
                    isinstance(anchor, dict) and
                    type(later.get("native_update")) is int and
                    type(anchor.get("native_update")) is int and
                    type(alignment.get("matched_update_run")) is int and
                    later["native_update"] == (anchor["native_update"] +
                                               alignment["matched_update_run"]))
    return (
        result.get("prefix_match") is False and
        result.get("input_prefix_match") is True and
        result.get("parity_verified") is False and
        alignment.get("kind") == "jfg-phase9-update-poll-alignment" and
        alignment.get("classification") == "poll-anchored-semantic-resynchronization" and
        alignment.get("alignment_validated") is False and
        alignment.get("parity_verified") is False and
        alignment.get("first_raw_mismatch_update") == first.get("update") and
        (native_ended or oracle_ended) and
        type(alignment.get("matched_update_run")) is int and
        alignment["matched_update_run"] >= 8 and
        isinstance(anchor, dict) and
        type(anchor.get("controller_polls")) is int and
        type(anchor.get("native_update")) is int and
        type(anchor.get("oracle_update")) is int)


def advance_update_diagnoses(store: JobStore, repo: Path, state: Path,
                             agent_binary: Path, *, max_new_jobs: int = 1) -> list[str]:
    """Queue read-only analysis of a sealed update mismatch; never a code fix."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known_ids = {item["job_id"] for item in projection}
    children = set()
    for item in projection:
        job = store.job(item["job_id"])
        if job["spec"]["inputs"] and job["spec"]["inputs"][0].startswith(
                "update-packet:"):
            child_packet = json.loads((state / "update-packets" /
                                       (item["job_id"] + ".json")).read_text(
                                           encoding="utf-8"))
            if "predecessor_id" in child_packet:
                children.add(child_packet["predecessor_id"])
    new_ids: list[str] = []
    for item in projection:
        if item["state"] != "passed":
            continue
        job_id = item["job_id"]
        job = store.job(job_id)
        if not job["spec"]["inputs"] or not job["spec"]["inputs"][0].startswith(
                "update-packet:"):
            continue
        if job_id in children:
            continue  # Superseded evidence is not a fresh diagnosis target.
        successor = update_diagnosis_id(job_id)
        if successor in known_ids:
            continue
        packet = json.loads((state / "update-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        validate_update_packet(packet, repo)
        if not execution.current(packet):
            continue  # Rebase the runtime/config identity before diagnosis.
        if any(file_sha256(Path(packet["pin_files"][key])) !=
               job["spec"]["pins"].get(key + "_sha256") for key in PIN_FILES):
            continue  # A changed build must be rebased before diagnosis.
        if (job["spec"]["inputs"] != ["update-packet:" + hashlib.sha256(
                canonical_bytes(packet)).hexdigest()] or
                not job["sealed_artifact"] or not job["sealed_sha256"]):
            raise SupervisorError("update diagnosis predecessor is not sealed")
        if not job["sealed_artifact"] or not job["sealed_sha256"]:
            raise SupervisorError("passed poll-pair baseline has no seal")
        sealed = Path(job["sealed_artifact"]).resolve(strict=True)
        if (not sealed.is_relative_to((state / "attempts" / job_id).resolve()) or
                sealed.name != "result.json" or
                file_sha256(sealed) != job["sealed_sha256"]):
            raise SupervisorError("update diagnosis predecessor seal changed")
        result = json.loads(sealed.read_text(encoding="utf-8"))
        if result.get("prefix_match") is not False:
            continue
        files = [sealed.parent / name for name in (
            "update-comparison.json", "update-alignment.json",
            "native/native-result.json", "oracle/oracle-result.json",
            "native/retrace-hashes.jsonl.updates.jsonl",
            "oracle/update-hashes.jsonl")]
        files.append(Path(packet["source_export"]) / "controller.input")
        if "focus_pair" in packet:
            files.append(sealed.parent / "focus-comparison.json")
        if result.get("input_poll_comparison_sha256") is not None:
            files.append(sealed.parent / "input-poll-comparison.json")
        report = json.loads(files[0].read_text(encoding="utf-8"))
        alignment = json.loads(files[1].read_text(encoding="utf-8"))
        if (result.get("complete") is not True or
                result.get("kind") != "update-execution" or
                result.get("job_id") != job_id or
                result.get("pins") != job["spec"]["pins"] or
                result.get("comparison_sha256") != file_sha256(files[0]) or
                result.get("alignment_diagnostic_sha256") != file_sha256(files[1]) or
                result.get("native_result_sha256") != file_sha256(files[2]) or
                result.get("oracle_result_sha256") != file_sha256(files[3]) or
                result.get("native_trace_sha256") != file_sha256(files[4]) or
                result.get("oracle_trace_sha256") != file_sha256(files[5]) or
                ("focus_pair" in packet and result.get("focus_comparison_sha256") !=
                    file_sha256(sealed.parent / "focus-comparison.json")) or
                (result.get("input_poll_comparison_sha256") is not None and
                    result["input_poll_comparison_sha256"] != file_sha256(
                        sealed.parent / "input-poll-comparison.json")) or
                result.get("first_divergence") != report.get("first_divergence") or
                result.get("alignment_classification") != alignment.get("classification") or
                result.get("parity_verified") is not False or
                report.get("kind") != "jfg-phase9-update-comparison" or
                alignment.get("kind") != "jfg-phase9-update-poll-alignment" or
                alignment.get("alignment_validated") is not False or
                alignment.get("parity_verified") is not False):
            raise SupervisorError("update diagnosis predecessor bundle is inconsistent")
        first = report.get("first_divergence") or {}
        if type(first.get("update")) is not int:
            continue
        anchor = alignment.get("same_poll_anchor")
        focus = (f"first raw update mismatch {first['update']}; "
                 f"poll-alignment classification {alignment['classification']}; "
                 f"same-poll anchor {anchor}; "
                 f"first later mismatch {alignment.get('first_later_mismatch')}")
        diagnosis_packet = {
            "schema": 1, "job_id": successor, "kind": "diagnose",
            "diagnosis_contract": bounded_diagnosis_contract(),
            "source_commit": packet["source_commit"],
            "pin_files": packet["pin_files"],
            "prompt": (
                "Read-only Phase 9 update-cadence diagnosis: " + focus +
                ". Read the pinned update comparison, poll-alignment report, "
                "both update traces, selected controller input, focused actor-byte "
                "report and input-poll comparison if present, and "
                "result manifests in the evidence list. "
                "Check the exact consumed controller values at the first later "
                "mismatch before proposing an input-index cause. "
                "Distinguish controller-poll timing, completed-update cadence, "
                "and actual game-state code divergence. The anchor is diagnostic, "
                "not parity proof. Identify a concrete root-cause hypothesis "
                "and one falsifiable next test. Do not change code, goldens, "
                "scheduler architecture, or timing policy.\nEvidence files:\n" +
                "\n".join(str(path.resolve(strict=True)) for path in files)),
            "timeout_seconds": 600, "validation": [],
            "prerequisites": [job_id], "retry_budget": 0,
            "allowed_paths": [], "max_changed_files": 0,
            "evidence_files": [{"path": str(path.resolve(strict=True)),
                                "sha256": file_sha256(path)} for path in files],
        }
        validate_packet(diagnosis_packet, repo)
        enqueue_packet(store, state, diagnosis_packet, agent_binary)
        known_ids.add(successor)
        new_ids.append(successor)
        if len(new_ids) >= max_new_jobs:
            break
    return new_ids


def advance_updates(store: JobStore, repo: Path, state: Path,
                    *, max_new_jobs: int = 1) -> list[str]:
    """Double a matching or safely resynchronized *diagnostic* prefix."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known_ids = {item["job_id"] for item in projection}
    children = set()
    for item in projection:
        job = store.job(item["job_id"])
        if job["spec"]["inputs"] and job["spec"]["inputs"][0].startswith(
                "update-packet:"):
            child_packet = json.loads((state / "update-packets" /
                                       (item["job_id"] + ".json")).read_text(
                                           encoding="utf-8"))
            if "predecessor_id" in child_packet:
                children.add(child_packet["predecessor_id"])
    new_ids: list[str] = []
    for item in projection:
        if item["state"] != "passed":
            continue
        job_id = item["job_id"]
        job = store.job(job_id)
        if not job["spec"]["inputs"] or not job["spec"]["inputs"][0].startswith(
                "update-packet:"):
            continue
        if job_id in children:
            continue  # Only a leaf can advance or be rebased.
        packet = json.loads((state / "update-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        validate_update_packet(packet, repo)
        final = json.loads((Path(packet["source_export"]) /
                            "export-manifest.json").read_text(
                                encoding="utf-8"))["oracle_final_frame"]
        current = packet["native_target"]
        packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (job["spec"]["inputs"] != ["update-packet:" + packet_sha] or
                job["spec"]["pins"].get("source_commit") != packet["source_commit"] or
                job["spec"]["prerequisites"] != [
                    packet.get("predecessor_id", packet["alignment_id"])] or
                not job["sealed_artifact"] or not job["sealed_sha256"]):
            raise SupervisorError("sealed update packet or pins changed")
        sealed = Path(job["sealed_artifact"]).resolve(strict=True)
        if (not sealed.is_relative_to((state / "attempts" / job_id).resolve()) or
                sealed.name != "result.json" or
                file_sha256(sealed) != job["sealed_sha256"]):
            raise SupervisorError("update result seal is invalid")
        result = json.loads(sealed.read_text(encoding="utf-8"))
        report_path = sealed.parent / "update-comparison.json"
        native_trace = sealed.parent / "native" / "retrace-hashes.jsonl.updates.jsonl"
        oracle_trace = sealed.parent / "oracle" / "update-hashes.jsonl"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (result.get("complete") is not True or
                result.get("kind") != "update-execution" or
                result.get("job_id") != job_id or
                result.get("packet_sha256") != packet_sha or
                result.get("pins") != job["spec"]["pins"] or
                result.get("comparison_sha256") != file_sha256(report_path) or
                result.get("prefix_match") is not report.get("match") or
                result.get("compared_updates") != report.get("compared_updates") or
                result.get("first_divergence") != report.get("first_divergence") or
                result.get("parity_verified") is not False or
                report.get("kind") != "jfg-phase9-update-comparison" or
                report.get("scope") != "prefix"):
            raise SupervisorError("sealed update bundle is inconsistent")
        if (result.get("native_trace_sha256") is None or
                result.get("oracle_trace_sha256") is None):
            continue  # Historical pre-trace-seal jobs cannot advance this frontier.
        if (result["native_trace_sha256"] != file_sha256(native_trace) or
                result["oracle_trace_sha256"] != file_sha256(oracle_trace)):
            raise SupervisorError("sealed update traces changed")
        if "execution" in packet:
            for side, check in (("native", execution.check_native),
                                ("oracle", execution.check_oracle)):
                path = sealed.parent / side / (side + "-result.json")
                if result.get(side + "_result_sha256") != file_sha256(path):
                    raise SupervisorError("sealed execution result changed")
                check(packet, json.loads(path.read_text(encoding="utf-8")))
        poll_path = sealed.parent / "input-poll-comparison.json"
        poll_verified = result.get("input_poll_comparison_sha256") is not None
        if poll_verified:
            poll_report = json.loads(poll_path.read_text(encoding="utf-8"))
            if (result["input_poll_comparison_sha256"] != file_sha256(poll_path) or
                    poll_report.get("kind") != "jfg-phase95-input-poll-comparison" or
                    poll_report.get("scope") != "prefix" or
                    poll_report.get("shared_prefix_polls") != result.get("compared_polls") or
                    (poll_report.get("first_input_mismatch") is None) is not
                    result.get("input_prefix_match")):
                raise SupervisorError("sealed input-poll comparison is inconsistent")
        current_hashes = {key: file_sha256(Path(packet["pin_files"][key]))
                          for key in PIN_FILES}
        if current_hashes["rom"] != job["spec"]["pins"]["rom_sha256"]:
            raise SupervisorError("ROM changed since sealed update capture")
        current_tool = update_tool_sha256(repo)
        runtime_changed = not execution.current(packet)
        changed = (current_hashes["native"] != job["spec"]["pins"]["native_sha256"] or
                   current_hashes["emulator"] != job["spec"]["pins"]["emulator_sha256"] or
                   current_tool != job["spec"]["pins"]["tool_sha256"] or runtime_changed)
        if changed:
            identity = ":".join((current_hashes["native"], current_hashes["emulator"],
                                 current_tool, str(current)))
            if "execution" in packet:
                identity += ":" + hashlib.sha256(canonical_bytes(execution.capture(
                    packet["pin_files"], packet["execution"]["profile"]))).hexdigest()
            successor = rebased_update_id(job_id, identity)
            target = current
        else:
            if "focus_pair" in packet:
                continue  # Focus is terminal until its pinned tools/build change.
            if (current >= final or not poll_verified or
                    result.get("input_prefix_match") is not True):
                continue
            if result["prefix_match"]:
                if result["first_divergence"] is not None:
                    raise SupervisorError("matching update report has a divergence")
            else:
                if "execution" in packet:
                    continue  # Same-index frontier: never extend a shifted suffix.
                alignment_path = sealed.parent / "update-alignment.json"
                if (result.get("alignment_diagnostic_sha256") is None or
                        result["alignment_diagnostic_sha256"] !=
                            file_sha256(alignment_path)):
                    raise SupervisorError("sealed update alignment changed")
                alignment = json.loads(alignment_path.read_text(encoding="utf-8"))
                if not diagnostic_suffix_allows_extension(result, alignment):
                    continue  # No supported diagnostic continuation.
            target = min(final, current * 2)
            successor = extended_update_id(job_id, target)
        if successor in known_ids:
            continue
        queue_update(store, repo, state, job_id=successor,
                     alignment_id=packet["alignment_id"],
                     alignment_result=sealed, alignment_packet=packet,
                     native_target=target, predecessor_id=job_id,
                     focus_pair=packet.get("focus_pair"))
        known_ids.add(successor)
        new_ids.append(successor)
        if len(new_ids) >= max_new_jobs:
            break
    return new_ids


def advance_update_focus(store: JobStore, repo: Path, state: Path,
                         *, max_new_jobs: int = 1) -> list[str]:
    """Recapture a new later mismatch, including one moved by a code fix."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known_ids = {item["job_id"] for item in projection}
    new_ids: list[str] = []
    for item in projection:
        if item["state"] != "passed":
            continue
        job_id = item["job_id"]
        job = store.job(job_id)
        if not job["spec"]["inputs"] or not job["spec"]["inputs"][0].startswith(
                "update-packet:"):
            continue
        successor = focused_update_id(job_id)
        if successor in known_ids:
            continue
        packet = json.loads((state / "update-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        validate_update_packet(packet, repo)
        if not execution.current(packet):
            continue
        if any(file_sha256(Path(packet["pin_files"][key])) !=
               job["spec"]["pins"].get(key + "_sha256") for key in PIN_FILES):
            continue  # Changed builds first need a deterministic rebase.
        if update_tool_sha256(repo) != job["spec"]["pins"].get("tool_sha256"):
            continue
        packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (job["spec"]["inputs"] != ["update-packet:" + packet_sha] or
                not job["sealed_artifact"] or not job["sealed_sha256"]):
            raise SupervisorError("focus predecessor is not sealed")
        sealed = Path(job["sealed_artifact"]).resolve(strict=True)
        if (not sealed.is_relative_to((state / "attempts" / job_id).resolve()) or
                sealed.name != "result.json" or
                file_sha256(sealed) != job["sealed_sha256"]):
            raise SupervisorError("focus predecessor seal changed")
        result = json.loads(sealed.read_text(encoding="utf-8"))
        alignment_path = sealed.parent / "update-alignment.json"
        if (result.get("complete") is not True or
                result.get("kind") != "update-execution" or
                result.get("job_id") != job_id or
                result.get("packet_sha256") != packet_sha or
                result.get("pins") != job["spec"]["pins"] or
                result.get("prefix_match") is not False or
                result.get("input_prefix_match") is not True or
                result.get("alignment_diagnostic_sha256") !=
                    file_sha256(alignment_path)):
            continue
        alignment = json.loads(alignment_path.read_text(encoding="utf-8"))
        later = alignment.get("first_later_mismatch") or {}
        if (alignment.get("kind") != "jfg-phase9-update-poll-alignment" or
                alignment.get("alignment_validated") is not False or
                alignment.get("parity_verified") is not False):
            continue
        if "execution" in packet:
            first = (result.get("first_divergence") or {}).get("update")
            pair = ({"native_before": first - 1, "oracle_before": first - 1,
                     "native_after": first, "oracle_after": first}
                    if type(first) is int and first > 1 else None)
            if pair == packet.get("focus_pair"):
                pair = None
        else:
            pair = focus_pair_for_later_mismatch(later, packet.get("focus_pair"))
        if pair is None:
            continue
        queue_update(store, repo, state, job_id=successor,
                     alignment_id=packet["alignment_id"],
                     alignment_result=sealed, alignment_packet=packet,
                     native_target=packet["native_target"],
                     predecessor_id=job_id, focus_pair=pair)
        known_ids.add(successor)
        new_ids.append(successor)
        if len(new_ids) >= max_new_jobs:
            break
    return new_ids


def advance_vi_boundaries(store: JobStore, repo: Path, state: Path,
                          *, max_new_jobs: int = 1) -> list[str]:
    """Queue replay-free analysis only from current, unsuperseded focus leaves."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known_ids = {item["job_id"] for item in projection}
    tool_identity = boundary_tool_sha256(repo)
    current_update_tool = update_tool_sha256(repo)
    children = set()
    for item in projection:
        job = store.job(item["job_id"])
        if (job["spec"]["inputs"] and job["spec"]["inputs"][0].startswith(
                "update-packet:")):
            packet = json.loads((state / "update-packets" /
                                 (item["job_id"] + ".json")).read_text(
                                     encoding="utf-8"))
            if "predecessor_id" in packet:
                children.add(packet["predecessor_id"])
    new_ids: list[str] = []
    for item in reversed(projection):
        if item["state"] != "passed":
            continue
        job_id = item["job_id"]
        if job_id in children:
            continue
        job = store.job(job_id)
        if not job["spec"]["inputs"] or not job["spec"]["inputs"][0].startswith(
                "update-packet:") or job["spec"]["pins"].get(
                    "tool_sha256") != current_update_tool:
            continue
        packet = json.loads((state / "update-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        if "focus_pair" not in packet:
            continue
        if min(packet["focus_pair"]["native_before"],
               packet["focus_pair"]["oracle_before"]) < 2:
            continue  # No preceding completed update for this VI comparison.
        if not execution.current(packet):
            continue
        if any(file_sha256(Path(packet["pin_files"][key])) !=
               job["spec"]["pins"].get(key + "_sha256") for key in PIN_FILES):
            continue
        successor = vi_boundary_id(job_id, tool_identity)
        if successor in known_ids:
            continue
        if not job["sealed_artifact"] or not job["sealed_sha256"]:
            raise SupervisorError("passed focused update lacks a seal")
        sealed = Path(job["sealed_artifact"])
        if file_sha256(sealed) != job["sealed_sha256"]:
            raise SupervisorError("focused update seal changed")
        result = json.loads(sealed.read_text(encoding="utf-8"))
        if (result.get("complete") is not True or
                result.get("oracle_vi_trace_sha256") is None or
                result.get("focus_comparison_sha256") is None):
            continue  # Older focused captures lack the required hook evidence.
        alignment_path = sealed.parent / "update-alignment.json"
        if (result.get("alignment_diagnostic_sha256") !=
                file_sha256(alignment_path)):
            continue
        alignment = json.loads(alignment_path.read_text(encoding="utf-8"))
        if "execution" in packet:
            first = (result.get("first_divergence") or {}).get("update")
            current_pair = ({"native_before": first - 1, "oracle_before": first - 1,
                             "native_after": first, "oracle_after": first}
                            if type(first) is int and first > 1 else None)
        else:
            current_pair = focus_pair_for_later_mismatch(
                alignment.get("first_later_mismatch") or {})
        if current_pair != packet["focus_pair"]:
            continue  # A rebase moved the onset beyond this old focus window.
        queue_boundary(store, repo, state, job_id=successor, focus_job_id=job_id)
        known_ids.add(successor)
        new_ids.append(successor)
        if len(new_ids) >= max_new_jobs:
            break
    return new_ids


def advance_vi_boundary_diagnoses(store: JobStore, repo: Path, state: Path,
                                  agent_binary: Path, *,
                                  max_new_jobs: int = 1) -> list[str]:
    """Diagnose the active sealed boundary report without authorizing edits."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known_ids = {item["job_id"] for item in projection}
    current_tool = boundary_tool_sha256(repo)
    new_ids: list[str] = []
    for item in projection:
        if item["state"] != "passed":
            continue
        job_id = item["job_id"]
        job = store.job(job_id)
        if (not job["spec"]["inputs"] or
                not job["spec"]["inputs"][0].startswith("vi-boundary-packet:") or
                job["spec"]["pins"].get("tool_sha256") != current_tool):
            continue
        boundary_packet = json.loads((state / "vi-boundary-packets" /
                                      (job_id + ".json")).read_text(encoding="utf-8"))
        validate_boundary_packet(boundary_packet, repo, state)
        digest = hashlib.sha256(canonical_bytes(boundary_packet)).hexdigest()
        if (job["spec"]["inputs"] != ["vi-boundary-packet:" + digest] or
                not job["sealed_artifact"] or not job["sealed_sha256"]):
            raise SupervisorError("VI-boundary diagnosis predecessor is not sealed")
        sealed = Path(job["sealed_artifact"]).resolve(strict=True)
        if (not sealed.is_relative_to((state / "attempts" / job_id).resolve()) or
                sealed.name != "result.json" or
                file_sha256(sealed) != job["sealed_sha256"]):
            raise SupervisorError("VI-boundary diagnosis seal changed")
        result = json.loads(sealed.read_text(encoding="utf-8"))
        vi_path = sealed.parent / "vi-boundary-comparison.json"
        transition_path = sealed.parent / "rdram-transition-comparison.json"
        if (result.get("complete") is not True or
                result.get("kind") != "vi-boundary-execution" or
                result.get("job_id") != job_id or
                result.get("packet_sha256") != digest or
                result.get("pins") != job["spec"]["pins"] or
                result.get("comparison_sha256") != file_sha256(vi_path) or
                result.get("rdram_transition_sha256") !=
                    file_sha256(transition_path) or
                result.get("alignment_validated") is not False or
                result.get("parity_verified") is not False):
            raise SupervisorError("VI-boundary diagnosis result is inconsistent")
        focus_id = boundary_packet["focus_job_id"]
        focus_result = Path(boundary_packet["focus_result_path"])
        focus_root = focus_result.parent
        focus_packet = json.loads((state / "update-packets" /
                                   (focus_id + ".json")).read_text(encoding="utf-8"))
        validate_update_packet(focus_packet, repo)
        if any(file_sha256(Path(focus_packet["pin_files"][key])) !=
               job["spec"]["pins"].get(key + "_sha256") for key in PIN_FILES):
            continue  # Historical capture remains sealed, but agent pins drifted.
        focus_path = focus_root / "focus-comparison.json"
        vi_report = json.loads(vi_path.read_text(encoding="utf-8"))
        focus_report = json.loads(focus_path.read_text(encoding="utf-8"))
        transition_report = json.loads(transition_path.read_text(encoding="utf-8"))
        facts = vi_boundary_diagnosis_facts(
            vi_report, focus_report, transition_report)
        identity = hashlib.sha256(canonical_bytes({
            "schema": 2, "boundary": job_id,
            "vi_sha256": file_sha256(vi_path),
            "focus_sha256": file_sha256(focus_path),
            "transition_sha256": file_sha256(transition_path),
        })).hexdigest()
        successor = vi_boundary_diagnosis_id(job_id, identity)
        if successor in known_ids:
            continue
        files = [
            sealed, vi_path, transition_path,
            focus_path,
            focus_root / "update-alignment.json",
            Path(focus_packet["source_export"]) / "controller.input",
            focus_root / "native" / "retrace-hashes.jsonl.updates.jsonl",
            focus_root / "oracle" / "update-hashes.jsonl",
            focus_root / "native" / "retrace-hashes.jsonl",
            focus_root / "oracle" / "consumed-vi-hashes.jsonl",
            focus_root / "native" / "native-result.json",
            focus_root / "oracle" / "oracle-result.json",
        ]
        packet = {
            "schema": 1, "job_id": successor, "kind": "diagnose",
            "diagnosis_contract": bounded_diagnosis_contract(),
            "source_commit": focus_packet["source_commit"],
            "pin_files": focus_packet["pin_files"],
            "prompt": (
                "Read-only Phase 9 VI-boundary diagnosis. Read the pinned "
                "boundary and RDRAM transition summaries first; inspect only "
                "bounded windows of the large traces near the reported updates. "
                "The following facts come from this pinned capture only, not "
                "an earlier boundary: " + json.dumps(facts, sort_keys=True) +
                ". Distinguish prior hidden-state, VI scheduling, hook-phase, "
                "and actual game-code hypotheses. "
                "Do not call any unclassified RDRAM page a gameplay global. "
                "Provide one concrete falsifiable next test tied to a code or "
                "memory location. Do not edit code, timing policy, or goldens, "
                "and do not claim validated alignment or parity.\nEvidence files:\n" +
                "\n".join(str(path.resolve(strict=True)) for path in files)),
            "timeout_seconds": 600, "validation": [],
            "prerequisites": [job_id], "retry_budget": 0,
            "allowed_paths": [], "max_changed_files": 0,
            "evidence_files": [{"path": str(path.resolve(strict=True)),
                                "sha256": file_sha256(path)} for path in files],
        }
        validate_packet(packet, repo)
        enqueue_packet(store, state, packet, agent_binary)
        known_ids.add(successor)
        new_ids.append(successor)
        if len(new_ids) >= max_new_jobs:
            break
    return new_ids


def advance_alignments(store: JobStore, repo: Path, state: Path,
                       *, max_new_jobs: int = 1) -> list[str]:
    """Queue a same-guest-update prefix capture after sealed VI alignment."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known_ids = {item["job_id"] for item in projection}
    new_ids: list[str] = []
    for item in projection:
        if item["state"] != "passed":
            continue
        job_id = item["job_id"]
        job = store.job(job_id)
        if not job["spec"]["inputs"] or not job["spec"]["inputs"][0].startswith(
                "alignment-packet:"):
            continue
        successor = update_id(job_id)
        if successor in known_ids:
            continue
        packet = json.loads((state / "alignment-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        validate_alignment_packet(packet, repo)
        packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (job["spec"]["inputs"] != ["alignment-packet:" + packet_sha] or
                job["spec"]["pins"].get("source_commit") != packet["source_commit"] or
                file_sha256(Path(packet["pin_files"]["rom"])) !=
                    job["spec"]["pins"].get("rom_sha256") or
                not job["sealed_artifact"] or not job["sealed_sha256"]):
            raise SupervisorError("sealed alignment packet or pins changed")
        sealed = Path(job["sealed_artifact"]).resolve(strict=True)
        if (not sealed.is_relative_to((state / "attempts" / job_id).resolve()) or
                sealed.name != "result.json" or
                file_sha256(sealed) != job["sealed_sha256"]):
            raise SupervisorError("alignment result seal is invalid")
        result = json.loads(sealed.read_text(encoding="utf-8"))
        report_path = sealed.parent / "alignment.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (result.get("complete") is not True or
                result.get("kind") != "alignment-execution" or
                result.get("job_id") != job_id or
                result.get("packet_sha256") != packet_sha or
                result.get("pins") != job["spec"]["pins"] or
                result.get("alignment_sha256") != file_sha256(report_path) or
                result.get("alignment_validated") is not False or
                result.get("parity_verified") is not False or
                report.get("alignment_validated") is not False or
                report.get("first_validated_gameplay_divergence") is not None):
            raise SupervisorError("sealed alignment bundle is inconsistent")
        queue_update(store, repo, state, job_id=successor,
                     alignment_id=job_id, alignment_result=sealed,
                     alignment_packet=packet)
        known_ids.add(successor)
        new_ids.append(successor)
        if len(new_ids) >= max_new_jobs:
            break
    return new_ids


def advance_comparisons(store: JobStore, repo: Path, state: Path,
                        agent_binary: Path, *, max_new_jobs: int = 1) -> list[str]:
    """Queue diagnoses for the oldest sealed mismatches, at most one per source."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known_ids = {item["job_id"] for item in projection}
    new_ids: list[str] = []
    for item in projection:
        if item["state"] != "passed":
            continue
        job_id = item["job_id"]
        job = store.job(job_id)
        inputs = job["spec"]["inputs"]
        if not inputs or not inputs[0].startswith("comparison-packet:"):
            continue
        successor = diagnosis_id(job_id)
        if successor in known_ids:
            continue
        packet_path = state / "comparison-packets" / (job_id + ".json")
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        validate_comparison_packet(packet, repo)
        packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (job["spec"]["inputs"] != ["comparison-packet:" + packet_sha] or
                job["spec"]["pins"]["source_commit"] != packet["source_commit"] or
                any(file_sha256(Path(packet["pin_files"][key])) !=
                    job["spec"]["pins"][key + "_sha256"] for key in PIN_FILES)):
            raise SupervisorError("sealed comparison packet or input pins changed")
        if not job["sealed_artifact"] or not job["sealed_sha256"]:
            raise SupervisorError("passed comparison has no sealed artifact")
        sealed = Path(job["sealed_artifact"]).resolve(strict=True)
        attempt_root = (state / "attempts" / job_id).resolve()
        if not sealed.is_relative_to(attempt_root) or sealed.name != "result.json" or \
                file_sha256(sealed) != job["sealed_sha256"]:
            raise SupervisorError("comparison result seal is invalid")
        result = json.loads(sealed.read_text(encoding="utf-8"))
        report_path = sealed.parent / "comparison.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (result.get("complete") is not True or
                result.get("kind") != "comparison-execution" or
                result.get("job_id") != job_id or
                result.get("packet_sha256") != packet_sha or
                result.get("pins") != job["spec"]["pins"] or
                result.get("comparison_sha256") != file_sha256(report_path) or
                result.get("match") is not report.get("match") or
                result.get("alignment_validated") is not False or
                result.get("parity_verified") is not False):
            raise SupervisorError("sealed comparison bundle is inconsistent")
        if report["match"]:
            continue  # A raw match alone cannot close the alignment/parity gate.
        queue_diagnosis_report(
            store, repo, state, agent_binary, job_id=successor,
            report_path=report_path, report=report,
            native_trace=Path(packet["native_trace"]["path"]),
            oracle_trace=Path(packet["oracle_trace"]["path"]),
            pin_files=packet["pin_files"],
            timeout_seconds=min(packet["timeout_seconds"], 900),
            source_commit=packet["source_commit"], prerequisites=[job_id])
        known_ids.add(successor)
        new_ids.append(successor)
        if len(new_ids) >= max_new_jobs:
            break
    return new_ids


def advance_diagnoses(store: JobStore, repo: Path, state: Path,
                      *, max_new_jobs: int = 1) -> list[str]:
    """Queue a bounded deterministic VI probe only for sealed misalignment."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known_ids = {item["job_id"] for item in projection}
    new_ids: list[str] = []
    for item in projection:
        if item["state"] != "passed":
            continue
        job_id = item["job_id"]
        job = store.job(job_id)
        inputs = job["spec"]["inputs"]
        if not inputs or not inputs[0].startswith("packet:"):
            continue
        successor = alignment_id(job_id)
        if successor in known_ids:
            continue
        packet_path = state / "packets" / (job_id + ".json")
        packet = read_packet(packet_path, repo)
        if packet["kind"] != "diagnose" or len(packet["prerequisites"]) != 1:
            continue
        predecessor = packet["prerequisites"][0]
        comparison_job = store.job(predecessor)
        if (not comparison_job["spec"]["inputs"] or not
                comparison_job["spec"]["inputs"][0].startswith("comparison-packet:")):
            continue  # Update and VI-boundary diagnoses have other successors.
        if comparison_job["state"] != "passed":
            raise SupervisorError("diagnosis predecessor is not a passed comparison")
        packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (inputs != ["packet:" + packet_sha] or
                job["spec"]["prerequisites"] != [predecessor] or
                not job["sealed_artifact"] or not job["sealed_sha256"]):
            raise SupervisorError("diagnosis packet or seal is incomplete")
        sealed = Path(job["sealed_artifact"]).resolve(strict=True)
        if (not sealed.is_relative_to((state / "attempts" / job_id).resolve()) or
                sealed.name != "result.json" or
                file_sha256(sealed) != job["sealed_sha256"]):
            raise SupervisorError("diagnosis result seal is invalid")
        result = json.loads(sealed.read_text(encoding="utf-8"))
        diagnosis_path = sealed.parent / "last-message.txt"
        diagnosis = read_diagnosis(diagnosis_path)
        if (result.get("complete") is not True or
                result.get("job_id") != job_id or
                result.get("packet_sha256") != packet_sha or
                result.get("pins") != job["spec"]["pins"] or
                result.get("diagnosis_sha256") != file_sha256(diagnosis_path) or
                result.get("diagnosis_schema_sha256") !=
                    file_sha256(diagnosis_schema_file(packet))):
            raise SupervisorError("sealed diagnosis bundle is inconsistent")
        if diagnosis["classification"] != "capture_misalignment" or \
                diagnosis["alignment"] == "validated":
            continue
        comparison_packet = json.loads((state / "comparison-packets" /
                                        (predecessor + ".json")).read_text(encoding="utf-8"))
        validate_comparison_packet(comparison_packet, repo)
        comparison_packet_sha = hashlib.sha256(
            canonical_bytes(comparison_packet)).hexdigest()
        if (comparison_job["spec"]["inputs"] !=
                ["comparison-packet:" + comparison_packet_sha] or
                not comparison_job["sealed_artifact"] or
                not comparison_job["sealed_sha256"]):
            raise SupervisorError("diagnosis predecessor packet or seal is incomplete")
        comparison_sealed = Path(comparison_job["sealed_artifact"]).resolve(strict=True)
        if (not comparison_sealed.is_relative_to(
                (state / "attempts" / predecessor).resolve()) or
                comparison_sealed.name != "result.json" or
                file_sha256(comparison_sealed) != comparison_job["sealed_sha256"]):
            raise SupervisorError("diagnosis predecessor seal is invalid")
        comparison_result = json.loads(comparison_sealed.read_text(encoding="utf-8"))
        if (comparison_result.get("complete") is not True or
                comparison_result.get("kind") != "comparison-execution" or
                comparison_result.get("job_id") != predecessor or
                comparison_result.get("packet_sha256") != comparison_packet_sha or
                comparison_result.get("pins") != comparison_job["spec"]["pins"] or
                comparison_result.get("match") is not False or
                comparison_result.get("alignment_validated") is not False):
            raise SupervisorError("diagnosis predecessor result is inconsistent")
        first = comparison_result.get("first_raw_divergence_retrace")
        if type(first) is not int or not 0 <= first <= 540:
            continue  # Prefix capture is unsuitable; requires checkpoint planning.
        target_frame = min(600, max(120, first + 60))
        queue_alignment(store, repo, state, job_id=successor,
                        diagnosis_id=job_id, diagnosis_path=diagnosis_path,
                        comparison_packet=comparison_packet,
                        target_frame=target_frame)
        known_ids.add(successor)
        new_ids.append(successor)
        if len(new_ids) >= max_new_jobs:
            break
    return new_ids


def advance_candidate_reviews(store: JobStore, repo: Path, state: Path,
                              agent_binary: Path,
                              *, max_new_jobs: int = 1) -> list[str]:
    """Queue one fresh, read-only review for each sealed implementation."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known_ids = {item["job_id"] for item in projection}
    new_ids = []
    for item in projection:
        if item["state"] != "passed":
            continue
        job_id = item["job_id"]
        inputs = store.job(job_id)["spec"]["inputs"]
        if not inputs or not inputs[0].startswith("packet:"):
            continue
        packet = read_packet(state / "packets" / (job_id + ".json"), repo)
        if packet["kind"] != "implement":
            continue
        successor = review_id(job_id)
        if successor in known_ids:
            continue
        queue_review(store, repo, state, agent_binary, job_id)
        new_ids.append(successor)
        known_ids.add(successor)
        if len(new_ids) >= max_new_jobs:
            break
    return new_ids


def advance_candidate_retests(store: JobStore, repo: Path, state: Path,
                              *, max_new_jobs: int = 1) -> list[str]:
    """Queue a pinned native differential only after an approved review."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known_ids = {item["job_id"] for item in projection}
    new_ids = []
    for item in projection:
        if item["state"] != "passed":
            continue
        job_id = item["job_id"]
        inputs = store.job(job_id)["spec"]["inputs"]
        if not inputs or not inputs[0].startswith("packet:"):
            continue
        packet = read_packet(state / "packets" / (job_id + ".json"), repo)
        if packet["kind"] != "review":
            continue
        successor = retest_id(job_id)
        if successor in known_ids:
            continue
        queued = queue_retest(store, repo, state, job_id)
        if queued is None:
            continue
        known_ids.add(queued)
        new_ids.append(queued)
        if len(new_ids) >= max_new_jobs:
            break
    return new_ids


def advance_determinism(store: JobStore, repo: Path, state: Path,
                        *, max_new_jobs: int = 1,
                        min_retraces: int = 4800) -> list[str]:
    """Start the partial-route 100-repeat gate once per current build/route."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known_ids = {item["job_id"] for item in projection}
    for item in reversed(projection):
        if item["state"] != "passed":
            continue
        baseline_id = item["job_id"]
        job = store.job(baseline_id)
        inputs = job["spec"]["inputs"]
        if not inputs or not inputs[0].startswith("update-packet:"):
            continue
        packet = json.loads((state / "update-packets" /
                             (baseline_id + ".json")).read_text(encoding="utf-8"))
        if type(packet.get("native_target")) is not int or \
                packet["native_target"] < min_retraces:
            continue
        native = Path(packet["pin_files"]["native"])
        if (not native.is_file() or
                file_sha256(native) != job["spec"]["pins"]["native_sha256"]):
            continue  # A historical executable pin is no longer current.
        validate_update_packet(packet, repo)
        if not execution.current(packet):
            continue
        source = Path(packet["source_export"])
        successor = determinism_id(
            file_sha256(source / "export-manifest.json"),
            job["spec"]["pins"]["native_sha256"], packet["source_commit"],
            packet["native_target"], 100, 4, packet.get("execution"))
        if successor in known_ids:
            return []
        queued = queue_determinism(store, repo, state, baseline_id,
                                   runs=100, parallelism=4)
        if queued != successor:
            raise SupervisorError("determinism job identity changed")
        return [queued]
    return []


def _current_sealed_poll_pair(store: JobStore, repo: Path, state: Path,
                              projection: list[dict], baseline_id: str,
                              baseline: dict) -> bool:
    """Reuse a capture only if its actual producers and input still match."""
    source = Path(baseline["source_export"])
    pin_files = baseline["pin_files"]
    expected_tools = {name: file_sha256(repo / name)
                      for name in POLL_PAIR_PLAN_TOOLS}
    expected = {
        "source_export": str(source.resolve(strict=True)),
        "source_manifest_sha256": file_sha256(source / "export-manifest.json"),
        "input_sha256": file_sha256(source / "controller.input"),
        "initial_flash_sha256": file_sha256(source / "initial.flash"),
        "initial_pak_sha256": file_sha256(source / "initial.pak"),
        "native_executable_sha256": file_sha256(Path(pin_files["native"])),
        "emulator_sha256": file_sha256(Path(pin_files["emulator"])),
        "emulator_runtime_sha256": runtime_digest(
            Path(pin_files["emulator"]).parent),
        "rom_sha256": file_sha256(Path(pin_files["rom"])),
        "target": 1500,
        "tool_sha256": expected_tools,
    }
    for item in reversed(projection):
        if item["state"] != "passed":
            continue
        pair_id = item["job_id"]
        pair_job = store.job(pair_id)
        if (not pair_job["spec"]["inputs"] or
                not pair_job["spec"]["inputs"][0].startswith("poll-pair-packet:") or
                pair_job["spec"]["prerequisites"] != [baseline_id]):
            continue
        context = poll_pair_context(store, state, pair_id)
        plan = json.loads((context["pair_root"] / "plan.json").read_text(
            encoding="utf-8"))
        if (context["packet"]["baseline_id"] == baseline_id and
                all(plan.get(key) == value for key, value in expected.items())):
            return True
    return False


def advance_poll_pairs(store: JobStore, repo: Path, state: Path,
                       *, max_new_jobs: int = 1) -> list[str]:
    """Queue a bounded, non-AI poll-state pair for the newest current mismatch."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known = {item["job_id"] for item in projection}
    tool = poll_pair_tool_sha256(repo)
    for item in reversed(projection):
        if item["state"] != "passed":
            continue
        baseline_id = item["job_id"]
        job = store.job(baseline_id)
        if (not job["spec"]["inputs"] or
                not job["spec"]["inputs"][0].startswith("update-packet:")):
            continue
        path = state / "update-packets" / (baseline_id + ".json")
        packet = json.loads(path.read_text(encoding="utf-8"))
        if "execution" in packet:
            continue  # Explicit profiles use strict-update focus, not legacy HLE jobs.
        if (type(packet.get("native_target")) is not int or
                type(packet.get("oracle_target")) is not int or
                min(packet["native_target"], packet["oracle_target"]) < 1500):
            continue
        native = Path(packet["pin_files"]["native"])
        emulator = Path(packet["pin_files"]["emulator"])
        if (not native.is_file() or not emulator.is_file() or
                file_sha256(native) != job["spec"]["pins"]["native_sha256"] or
                file_sha256(emulator) != job["spec"]["pins"]["emulator_sha256"]):
            continue  # Do not act on a historical binary or emulator profile.
        sealed = Path(job["sealed_artifact"]).resolve(strict=True)
        if (not sealed.is_relative_to((state / "attempts" / baseline_id).resolve()) or
                file_sha256(sealed) != job["sealed_sha256"]):
            raise SupervisorError("poll-pair baseline seal changed")
        result = json.loads(sealed.read_text(encoding="utf-8"))
        if result.get("first_divergence") is None:
            continue
        if _current_sealed_poll_pair(store, repo, state, projection,
                                     baseline_id, packet):
            return []
        successor = poll_pair_id(baseline_id, 1500, tool,
                                 job["spec"]["pins"]["native_sha256"])
        if successor in known:
            return []
        queued = queue_poll_pair(store, repo, state, baseline_id,
                                 target=1500, timeout=600)
        if queued != successor:
            raise SupervisorError("poll-pair job identity changed")
        return [queued]
    return []


def advance_poll_lags(store: JobStore, repo: Path, state: Path,
                      *, max_new_jobs: int = 1) -> list[str]:
    """Analyze the newest sealed poll pair for exact nearby state recurrence."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known = {item["job_id"] for item in projection}
    tool = poll_lag_tool_sha256(repo)
    for item in reversed(projection):
        if item["state"] != "passed":
            continue
        pair_id = item["job_id"]
        job = store.job(pair_id)
        if (not job["spec"]["inputs"] or
                not job["spec"]["inputs"][0].startswith("poll-pair-packet:")):
            continue
        successor = poll_lag_id(pair_id, 8, tool)
        if successor in known:
            return []
        queued = queue_poll_lag(store, repo, state, pair_id, radius=8)
        if queued != successor:
            raise SupervisorError("poll-lag job identity changed")
        return [queued]
    return []


def advance_poll_lag_diagnoses(store: JobStore, repo: Path, state: Path,
                               agent_binary: Path, *,
                               max_new_jobs: int = 1) -> list[str]:
    """Queue read-only clock research, never a patch, from sealed lag evidence."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known = {item["job_id"] for item in projection}
    for item in reversed(projection):
        if item["state"] != "passed":
            continue
        lag_id = item["job_id"]
        job = store.job(lag_id)
        if (not job["spec"]["inputs"] or
                not job["spec"]["inputs"][0].startswith("poll-lag-packet:")):
            continue
        event_context = None
        event_pending = False
        for candidate in reversed(projection):
            event_id = candidate["job_id"]
            event_job = store.job(event_id)
            if (not event_job["spec"]["inputs"] or
                    not event_job["spec"]["inputs"][0].startswith(
                        "event-pair-packet:")):
                continue
            event_packet = json.loads((state / "event-pair-packets" /
                                       (event_id + ".json")).read_text(
                                           encoding="utf-8"))
            if event_packet.get("lag_id") != lag_id:
                continue
            if candidate["state"] in ("queued", "leased", "running", "verifying"):
                event_pending = True
            elif candidate["state"] == "passed":
                event_context = sealed_event_pair_context(
                    store, repo, state, event_id)
            break
        if event_pending:
            continue  # Let the model-free capture finish before diagnosis.
        focus_context = None
        focus_pending = False
        if event_context is not None:
            for candidate in reversed(projection):
                focus_id = candidate["job_id"]
                focus_job = store.job(focus_id)
                if (not focus_job["spec"]["inputs"] or
                        not focus_job["spec"]["inputs"][0].startswith(
                            "input-focus-packet:")):
                    continue
                focus_packet = json.loads((state / "input-focus-packets" /
                                           (focus_id + ".json")).read_text(
                                               encoding="utf-8"))
                if focus_packet.get("event_id") != event_id:
                    continue
                if candidate["state"] in ("queued", "leased", "running",
                                          "verifying"):
                    focus_pending = True
                elif candidate["state"] == "passed":
                    focus_context = sealed_input_focus_context(
                        store, repo, state, focus_id)
                break
        if focus_pending:
            continue  # Keep model diagnosis behind the exact-input capture.
        clock_evidence = (derive_update_poll_evidence(
            state, event_id, event_context, repo)
            if event_context is not None else None)
        clock_digest = (file_sha256(clock_evidence[0])
                        if clock_evidence is not None else None)
        successor = diagnosis_id(lag_id)
        if focus_context is not None:
            successor = focus_diagnosis_id(
                lag_id, file_sha256(focus_context["report_path"]),
                clock_digest)
        elif clock_digest is not None:
            successor = clock_diagnosis_id(lag_id, clock_digest)
        if successor in known:
            prior = store.job(successor)
            current_tool = tool_identity_sha256(agent_binary)
            if (prior["state"] != "blocked" or
                    prior["spec"]["pins"]["tool_sha256"] == current_tool):
                return []
            successor = successor + "-tool-" + current_tool[:12]
            if successor in known:
                return []
        packet = json.loads((state / "poll-lag-packets" /
                             (lag_id + ".json")).read_text(encoding="utf-8"))
        validate_poll_lag_packet(packet, repo, state)
        context = poll_pair_context(store, state, packet["pair_job_id"])
        if not job["sealed_artifact"] or not job["sealed_sha256"]:
            raise SupervisorError("poll-lag diagnosis predecessor has no seal")
        sealed = Path(job["sealed_artifact"]).resolve(strict=True)
        if (not sealed.is_relative_to((state / "attempts" / lag_id).resolve()) or
                sealed.name != "result.json" or
                file_sha256(sealed) != job["sealed_sha256"]):
            raise SupervisorError("poll-lag diagnosis predecessor seal changed")
        packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        result = json.loads(sealed.read_text(encoding="utf-8"))
        report_path = sealed.parent / "lag-report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (job["spec"]["inputs"] != ["poll-lag-packet:" + packet_sha] or
                job["spec"]["prerequisites"] != [packet["pair_job_id"]] or
                packet["source_export"] != str(context["source"]) or
                packet["pair_root"] != str(context["pair_root"]) or
                result.get("complete") is not True or
                result.get("kind") != "poll-lag-execution" or
                result.get("job_id") != lag_id or
                result.get("packet_sha256") != packet_sha or
                result.get("pins") != job["spec"]["pins"] or
                result.get("lag_report_sha256") != file_sha256(report_path) or
                report.get("kind") != "jfg-phase9-poll-lag-analysis" or
                report.get("comparison_sha256") != file_sha256(
                    context["pair_root"] / "comparison.json") or
                any(report.get(key) != result.get(key) for key in (
                    "mismatching_polls", "unique_shift_match",
                    "ambiguous_shift_match", "no_shift_match")) or
                report.get("alignment_validated") is not False or
                report.get("parity_verified") is not False or
                result.get("alignment_validated") is not False or
                result.get("parity_verified") is not False):
            raise SupervisorError("poll-lag diagnosis evidence is inconsistent")
        if type(report["mismatching_polls"]) is not int or \
                report["mismatching_polls"] < 1:
            continue
        pair_root, source = context["pair_root"], context["source"]
        phase_path = sealed.parent / "call-phase-report.json"
        phase_digest = result.get("call_phase_report_sha256")
        if phase_digest is not None:
            if (not isinstance(phase_digest, str) or
                    not phase_path.is_file() or
                    file_sha256(phase_path) != phase_digest):
                raise SupervisorError("poll call-phase report seal changed")
            phase = json.loads(phase_path.read_text(encoding="utf-8"))
            if (phase.get("kind") != "jfg-phase9-poll-call-phase" or
                    phase.get("polls_compared") != report["compared_polls"] or
                    phase.get("native_sha256") != file_sha256(
                        pair_root / "native" / "retrace-hashes.jsonl.polls.jsonl") or
                    phase.get("oracle_sha256") != file_sha256(
                        pair_root / "oracle" / "poll-hashes.jsonl") or
                    phase.get("same_call_phase") != result.get("same_call_phase") or
                    phase.get("hooks_observed") !=
                        result.get("call_phase_hooks_observed") or
                    phase.get("alignment_validated") is not False or
                    phase.get("parity_verified") is not False):
                raise SupervisorError("poll call-phase report is inconsistent")
        elif result.get("same_call_phase") is not None or \
                result.get("call_phase_hooks_observed") is not None:
            raise SupervisorError("poll call-phase result has no report seal")
        files = [sealed, report_path,
                 pair_root / "pair-result.json", pair_root / "comparison.json",
                 pair_root / "native" / "retrace-hashes.jsonl.polls.jsonl",
                 pair_root / "oracle" / "poll-hashes.jsonl",
                 source / "controller.input",
                 pair_root / "native" / "native-result.json",
                 pair_root / "oracle" / "oracle-result.json",
                 source / "initial.flash", source / "initial.pak",
                 phase_path if phase_digest is not None else pair_root / "plan.json"]
        event_guidance = ""
        if event_context is not None:
            if (event_context["packet"]["pair_id"] != packet["pair_job_id"] or
                    event_context["packet"]["lag_id"] != lag_id):
                raise SupervisorError("event-pair diagnosis lineage changed")
            files = [report_path,
                     phase_path if phase_digest is not None else sealed,
                     event_context["sealed"], event_context["report_path"],
                     event_context["native_trace"],
                     event_context["oracle_trace"],
                     pair_root / "comparison.json",
                     pair_root / "native" / "retrace-hashes.jsonl.polls.jsonl",
                     pair_root / "oracle" / "poll-hashes.jsonl",
                     source / "controller.input", source / "initial.flash",
                     source / "initial.pak"]
            event_guidance = (
                "Read the sealed event-order report and both bounded raw event "
                "traces before proposing another test. Distinguish VI cadence "
                "from completed game updates and exact sampled input; event "
                "order does not prove within-call consumption, initial Pak "
                "equivalence, or aligned gameplay. ")
            if event_context.get("update_alignment_path") is not None:
                files[2] = event_context["update_alignment_path"]
                event_guidance += (
                    "Read the sealed update-alignment report: a matching "
                    "completed-update prefix can coexist with poll-clock "
                    "drift. Its first same-numbered state difference is a "
                    "diagnostic frontier, not proof of a gameplay-code bug. ")
            if focus_context is not None:
                if focus_context["packet"]["event_id"] != event_id:
                    raise SupervisorError("input-focus diagnosis lineage changed")
                if event_context.get("update_alignment_path") is not None:
                    files[7] = event_context["update_alignment_path"]
                files[2] = focus_context["report_path"]
                update_frontier = focus_context["alignment"]
                first_update = update_frontier["first_semantic_difference"]
                event_guidance += (
                    "Read the sealed game-visible input-buffer comparison "
                    "at the first divergent completed update. Matching "
                    "buffers rule out a simple dropped delivered sample at "
                    "that boundary but do not establish all within-call "
                    "reads or initial Pak equivalence. The verified update "
                    f"streams match for {update_frontier['matching_update_prefix']} "
                    "completed updates; the first same-update state "
                    f"difference is update {first_update['update']}. ")
            if clock_evidence is not None:
                clock_path, clock_report = clock_evidence
                diagnostic = clock_report["diagnostic"]
                files[6] = clock_path
                anchor = diagnostic.get("same_poll_anchor")
                event_guidance += (
                    "Read the pinned model-free update/poll alignment report. "
                    "Its classification is " + diagnostic["classification"] +
                    "; matched offset-paired update run is " +
                    str(diagnostic["matched_update_run"]) + ". " +
                    ("The candidate same-poll anchor is poll " +
                     str(anchor["controller_polls"]) + " at native update " +
                     str(anchor["native_update"]) + " and oracle update " +
                     str(anchor["oracle_update"]) + ". "
                     if anchor is not None else "") +
                    "This report does not validate end-to-end alignment, "
                    "initial Pak state, or a gameplay implementation fix. ")
        diagnosis_packet = {
            "schema": 1, "job_id": successor, "kind": "diagnose",
            "diagnosis_contract": bounded_diagnosis_contract(),
            "source_commit": _git_ok(repo, "rev-parse", "HEAD"),
            "pin_files": context["packet"]["pin_files"],
            "prompt": (
                "Read-only Phase 9 poll-cadence diagnosis. Same-numbered "
                "controller inputs match, but the poll-state report is not "
                "aligned parity evidence. " + event_guidance +
                "Read the pinned lag report and evidence first; inspect only "
                "bounded trace windows near "
                "the first mismatch and unmatched polls. If present, use "
                "the call-phase report to test the controller-hook hypothesis; "
                "it does not establish full alignment. Exact states at "
                "shifted polls are hypotheses, not permission to shift or "
                "omit input. Check hook phase, completed-update cadence, "
                "and unknown oracle Pak state. Propose one falsifiable "
                "instrumentation test; first_supported_retrace must be null "
                "unless an exact common boundary is independently proved. "
                "Do not edit code, goldens, timing policy, or claim parity.\n"
                "Evidence files:\n" + "\n".join(str(path) for path in files)),
            "timeout_seconds": 600, "validation": [],
            "prerequisites": [lag_id] + (
                [focus_context["packet"]["job_id"]]
                if focus_context is not None else []),
            "retry_budget": 0,
            "allowed_paths": [], "max_changed_files": 0,
            "evidence_files": [{"path": str(path.resolve(strict=True)),
                                "sha256": file_sha256(path)} for path in files],
        }
        validate_packet(diagnosis_packet, repo)
        enqueue_packet(store, state, diagnosis_packet, agent_binary)
        return [successor]
    return []


def advance_event_pairs(store: JobStore, repo: Path, state: Path,
                        *, max_new_jobs: int = 1) -> list[str]:
    """Queue the first supported bounded event trace after a sealed lag job."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known = {item["job_id"] for item in projection}
    for item in reversed(projection):
        if item["state"] != "passed":
            continue
        lag_id = item["job_id"]
        lag = store.job(lag_id)
        if (not lag["spec"]["inputs"] or
                not lag["spec"]["inputs"][0].startswith("poll-lag-packet:")):
            continue
        lag_packet_path = state / "poll-lag-packets" / (lag_id + ".json")
        lag_packet = json.loads(lag_packet_path.read_text(encoding="utf-8"))
        pair_job = store.job(lag_packet["pair_job_id"])
        pair_packet = json.loads((state / "poll-pair-packets" /
                                  (lag_packet["pair_job_id"] + ".json")).read_text(
                                      encoding="utf-8"))
        native = Path(pair_packet["pin_files"]["native"])
        if (not native.is_file() or
                file_sha256(native) != pair_job["spec"]["pins"]["native_sha256"]):
            continue  # A changed native build needs a fresh poll-pair baseline.
        if not event_capable(native):
            continue  # Old native builds cannot emit the event trace.
        context = event_pair_context(store, repo, state, lag_id)
        windows = derive_event_windows(context["report"])
        for existing in reversed(projection):
            existing_id = existing["job_id"]
            existing_job = store.job(existing_id)
            if (not existing_job["spec"]["inputs"] or
                    not existing_job["spec"]["inputs"][0].startswith(
                        "event-pair-packet:")):
                continue
            existing_packet = json.loads((state / "event-pair-packets" /
                                          (existing_id + ".json")).read_text(
                                              encoding="utf-8"))
            if (existing_packet.get("lag_id") != lag_id or
                    existing_packet.get("event_windows") !=
                        [list(window) for window in windows] or
                    existing_job["spec"]["pins"]["native_sha256"] !=
                        pair_job["spec"]["pins"]["native_sha256"]):
                continue
            if existing["state"] == "passed":
                sealed = sealed_event_pair_context(
                    store, repo, state, existing_id)
                if sealed["caller_report"] is not None:
                    return []  # Preserve capture with caller discovery.
                continue  # Historical capture cannot select a return hook.
            if existing["state"] in ("queued", "leased", "running", "verifying"):
                return []
        successor = event_pair_id(lag_id, windows, event_pair_tool_sha256(repo),
                                  pair_job["spec"]["pins"]["native_sha256"])
        if successor in known:
            return []
        queued = queue_event_pair(store, repo, state, lag_id)
        if queued != successor:
            raise SupervisorError("event-pair job identity changed")
        return [queued]
    return []


def advance_controller_returns(store: JobStore, repo: Path, state: Path,
                               *, max_new_jobs: int = 1) -> list[str]:
    """Queue a bounded return-byte comparison from sealed caller evidence."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    for item in reversed(projection):
        if item["state"] != "passed":
            continue
        event_id = item["job_id"]
        event_job = store.job(event_id)
        if (not event_job["spec"]["inputs"] or
                not event_job["spec"]["inputs"][0].startswith(
                    "event-pair-packet:")):
            continue
        context = sealed_event_pair_context(store, repo, state, event_id)
        caller_report = context["caller_report"]
        if caller_report is None:
            continue  # Historical event captures predate caller discovery.
        callers = {window["unique_caller"] for window in
                   caller_report["windows"] if window["rows"] > 0}
        if (len(callers) != 1 or None in callers or
                sum(window["rows"] for window in
                    caller_report["windows"]) == 0):
            continue  # A single return hook cannot represent this capture.
        event_packet = context["packet"]
        native = Path(event_packet["pin_files"]["native"])
        if (not native.is_file() or file_sha256(native) !=
                event_job["spec"]["pins"]["native_sha256"]):
            continue
        if not controller_return_capable(native):
            candidates = {}
            for donor in projection:
                if donor["state"] != "passed":
                    continue
                donor_id = donor["job_id"]
                donor_job = store.job(donor_id)
                if (not donor_job["spec"]["inputs"] or
                        not donor_job["spec"]["inputs"][0].startswith(
                            "controller-return-packet:")):
                    continue
                donor_context = sealed_controller_return_context(
                    store, repo, state, donor_id)
                donor_packet = donor_context["packet"]
                if any(donor_packet["pin_files"][key] !=
                       event_packet["pin_files"][key]
                       for key in ("rom", "emulator")):
                    continue
                candidate = Path(donor_packet["pin_files"]["native"])
                if (not candidate.is_file() or
                        file_sha256(candidate) !=
                        donor_job["spec"]["pins"]["native_sha256"] or
                        not controller_return_capable(candidate)):
                    continue
                key = (donor_packet["native_runtime_sha256"],
                       donor_job["spec"]["pins"]["native_sha256"])
                candidates.setdefault(key, []).append(candidate)
            if len(candidates) != 1:
                continue  # No verified upgrade, or competing runtime pins.
            native = sorted(next(iter(candidates.values())), key=str)[0]
        return_pc = next(iter(callers))
        selected_pins = {**event_packet["pin_files"], "native": str(native)}
        for previous in reversed(projection):
            previous_id = previous["job_id"]
            previous_job = store.job(previous_id)
            if (not previous_job["spec"]["inputs"] or
                    not previous_job["spec"]["inputs"][0].startswith(
                        "controller-return-packet:")):
                continue
            packet_path = (state / "controller-return-packets" /
                           (previous_id + ".json"))
            previous_packet = json.loads(packet_path.read_text(
                encoding="utf-8"))
            if (previous_packet.get("source_export") !=
                    event_packet["source_export"] or
                    previous_packet.get("pin_files") !=
                    selected_pins or
                    previous_packet.get("target") != event_packet["target"] or
                    previous_packet.get("event_windows") !=
                    event_packet["event_windows"] or
                    previous_packet.get("return_pc") != return_pc):
                continue
            if previous["state"] == "passed":
                sealed_controller_return_context(
                    store, repo, state, previous_id)
                if previous_packet.get("caller_event_id") is not None:
                    return []  # A linked probe covers these exact pins.
                continue  # Older unlinked probe lacks caller provenance.
            if previous["state"] in (
                    "queued", "leased", "running", "verifying"):
                return []
        pins = event_packet["pin_files"]
        queued = queue_controller_return(
            store, repo, state, Path(event_packet["source_export"]),
            native, Path(pins["emulator"]), Path(pins["rom"]),
            file_sha256(Path(pins["rom"])), target=event_packet["target"],
            windows=tuple(tuple(window) for window in
                          event_packet["event_windows"]),
            return_pc=int(return_pc, 16),
            timeout=event_packet["timeout_seconds"],
            caller_event_id=event_id)
        return [queued]
    return []


def advance_runtime_poll_pairs(store: JobStore, repo: Path, state: Path,
                               *, max_new_jobs: int = 1) -> list[str]:
    """Refresh poll/update baseline under a sealed upgraded native runtime."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known = {item["job_id"] for item in projection}
    for item in reversed(projection):
        if item["state"] != "passed":
            continue
        predecessor_id = item["job_id"]
        job = store.job(predecessor_id)
        if (not job["spec"]["inputs"] or not job["spec"]["inputs"][0].startswith(
                "controller-return-packet:")):
            continue
        context = sealed_controller_return_context(
            store, repo, state, predecessor_id)
        packet = context["packet"]
        if ("caller_event_id" not in packet or packet["target"] < 1500):
            continue  # Only discovery-linked upgrades establish new baselines.
        event = sealed_event_pair_context(
            store, repo, state, packet["caller_event_id"])
        if (packet["pin_files"]["native"] ==
                event["packet"]["pin_files"]["native"]):
            continue  # Same runtime must not start a capture feedback cycle.
        successor = poll_pair_id(
            predecessor_id, 1500, poll_pair_tool_sha256(repo),
            job["spec"]["pins"]["native_sha256"])
        if successor in known:
            existing = store.job(successor)
            if existing["state"] == "passed":
                poll_pair_context(store, state, successor)
            return []
        return [queue_from_controller_return(
            store, repo, state, predecessor_id, target=1500)]
    return []


def advance_input_focus_pairs(store: JobStore, repo: Path, state: Path,
                              *, max_new_jobs: int = 1) -> list[str]:
    """Queue exact game-visible input snapshots at the first update frontier."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    if (state / "PAUSED").exists():
        return []
    projection = store.status_projection()["jobs"]
    known = {item["job_id"] for item in projection}
    for item in reversed(projection):
        if item["state"] != "passed":
            continue
        event_id = item["job_id"]
        event_job = store.job(event_id)
        if (not event_job["spec"]["inputs"] or
                not event_job["spec"]["inputs"][0].startswith(
                    "event-pair-packet:")):
            continue
        event_packet = json.loads((state / "event-pair-packets" /
                                   (event_id + ".json")).read_text(
                                       encoding="utf-8"))
        native = Path(event_packet["pin_files"]["native"])
        if (not native.is_file() or
                file_sha256(native) !=
                event_job["spec"]["pins"]["native_sha256"]):
            continue
        try:
            context = input_focus_context(store, repo, state, event_id)
        except ValueError as error:
            if str(error) == "no bounded first divergent update in the predecessor":
                continue
            raise
        for existing in reversed(projection):
            existing_id = existing["job_id"]
            existing_job = store.job(existing_id)
            if (not existing_job["spec"]["inputs"] or
                    not existing_job["spec"]["inputs"][0].startswith(
                        "input-focus-packet:")):
                continue
            existing_packet = json.loads((state / "input-focus-packets" /
                                          (existing_id + ".json")).read_text(
                                              encoding="utf-8"))
            if (existing_packet.get("event_id") != event_id or
                    existing_packet.get("focus_updates") !=
                        list(context["focus"]) or
                    existing_job["spec"]["pins"]["native_sha256"] !=
                    event_job["spec"]["pins"]["native_sha256"]):
                continue
            if existing["state"] == "passed":
                sealed_input_focus_context(store, repo, state, existing_id)
                return []
            if existing["state"] in ("queued", "leased", "running",
                                     "verifying"):
                return []
        successor = input_focus_id(
            event_id, context["focus"], input_focus_tool_sha256(repo),
            event_job["spec"]["pins"]["native_sha256"])
        if successor in known:
            return []
        queued = queue_input_focus(store, repo, state, event_id)
        if queued != successor:
            raise SupervisorError("input-focus job identity changed")
        return [queued]
    return []


def _advance_phase9_jobs(store: JobStore, repo: Path, state: Path,
                         agent_binary: Path, *, max_new_jobs: int = 1) -> list[str]:
    """Advance the earliest actionable Phase 9 evidence one bounded step."""
    extended = advance_updates(store, repo, state,
                               max_new_jobs=max_new_jobs)
    if len(extended) == max_new_jobs:
        return extended
    focused = advance_update_focus(store, repo, state,
                                   max_new_jobs=max_new_jobs - len(extended))
    if len(extended) + len(focused) == max_new_jobs:
        return extended + focused
    boundaries = advance_vi_boundaries(
        store, repo, state,
        max_new_jobs=max_new_jobs - len(extended) - len(focused))
    if len(extended) + len(focused) + len(boundaries) == max_new_jobs:
        return extended + focused + boundaries
    boundary_diagnoses = advance_vi_boundary_diagnoses(
        store, repo, state, agent_binary,
        max_new_jobs=max_new_jobs - len(extended) - len(focused) - len(boundaries))
    if len(extended) + len(focused) + len(boundaries) + len(boundary_diagnoses) == max_new_jobs:
        return extended + focused + boundaries + boundary_diagnoses
    update_diagnoses = advance_update_diagnoses(
        store, repo, state, agent_binary,
        max_new_jobs=max_new_jobs - len(extended) - len(focused) - len(boundaries) -
        len(boundary_diagnoses))
    if len(extended) + len(focused) + len(boundaries) + len(boundary_diagnoses) + len(update_diagnoses) == max_new_jobs:
        return extended + focused + boundaries + boundary_diagnoses + update_diagnoses
    updates = advance_alignments(store, repo, state,
                                 max_new_jobs=max_new_jobs - len(extended) -
                                 len(focused) - len(boundaries) - len(boundary_diagnoses) - len(update_diagnoses))
    if len(extended) + len(focused) + len(boundaries) + len(boundary_diagnoses) + len(update_diagnoses) + len(updates) == max_new_jobs:
        return extended + focused + boundaries + boundary_diagnoses + update_diagnoses + updates
    diagnoses = advance_diagnoses(store, repo, state,
                                  max_new_jobs=max_new_jobs - len(extended) -
                                  len(focused) - len(boundaries) - len(boundary_diagnoses) - len(update_diagnoses) - len(updates))
    if len(extended) + len(focused) + len(boundaries) + len(boundary_diagnoses) + len(update_diagnoses) + len(updates) + len(diagnoses) == max_new_jobs:
        return extended + focused + boundaries + boundary_diagnoses + update_diagnoses + updates + diagnoses
    comparisons = advance_comparisons(
        store, repo, state, agent_binary,
        max_new_jobs=max_new_jobs - len(extended) - len(focused) - len(boundaries) - len(boundary_diagnoses) - len(update_diagnoses) -
        len(updates) - len(diagnoses))
    return extended + focused + boundaries + boundary_diagnoses + update_diagnoses + updates + diagnoses + comparisons


def advance_jobs(store: JobStore, repo: Path, state: Path,
                 agent_binary: Path, *, max_new_jobs: int = 1) -> list[str]:
    """Prioritize review/retest, poll diagnosis, repeatability, then Phase 9."""
    if type(max_new_jobs) is not int or not 1 <= max_new_jobs <= 16:
        raise SupervisorError("max_new_jobs must be 1..16")
    from scripts.autonomy.branch_count_repair import advance as advance_proven_repairs
    from scripts.autonomy.candidate_feedback import advance as advance_candidate_feedback
    from scripts.autonomy.state_word_experiment import advance as advance_state_word_experiments
    from scripts.autonomy.experiment_feedback import advance as advance_experiment_feedback
    from scripts.autonomy.entry_experiment import advance as advance_entry_experiments
    from scripts.autonomy.point_experiment import advance as advance_point_experiments
    from scripts.autonomy.interval_experiment import advance as advance_interval_experiments
    from scripts.autonomy.device_experiment import advance as advance_device_experiments
    from scripts.autonomy.count_ledger_experiment import advance as advance_count_ledgers
    from scripts.autonomy.research_completion import advance as advance_research_completions
    steps = (
        lambda n: advance_candidate_reviews(store, repo, state, agent_binary,
                                            max_new_jobs=n),
        lambda n: advance_candidate_retests(store, repo, state, max_new_jobs=n),
        lambda n: advance_proven_repairs(store, repo, state, agent_binary, max_new_jobs=n),
        lambda n: advance_candidate_feedback(store, repo, state, agent_binary, max_new_jobs=n),
        lambda n: advance_experiment_feedback(store, repo, state, agent_binary, max_new_jobs=n),
        lambda n: advance_research_completions(store, repo, state, agent_binary, max_new_jobs=n),
        lambda n: advance_state_word_experiments(store, repo, state, agent_binary, max_new_jobs=n),
        lambda n: advance_entry_experiments(store, repo, state, agent_binary, max_new_jobs=n),
        lambda n: advance_point_experiments(store, repo, state, agent_binary, max_new_jobs=n),
        lambda n: advance_interval_experiments(store, repo, state, agent_binary, max_new_jobs=n),
        lambda n: advance_device_experiments(store, repo, state, agent_binary, max_new_jobs=n),
        lambda n: advance_count_ledgers(store, repo, state, agent_binary, max_new_jobs=n),
        lambda n: ([job] if (job := queue_frontier_next(store, repo, state))
                   else []),
        lambda n: advance_poll_lags(store, repo, state, max_new_jobs=n),
        lambda n: advance_event_pairs(store, repo, state, max_new_jobs=n),
        lambda n: advance_controller_returns(store, repo, state,
                                             max_new_jobs=n),
        lambda n: advance_runtime_poll_pairs(store, repo, state,
                                             max_new_jobs=n),
        lambda n: advance_input_focus_pairs(store, repo, state,
                                            max_new_jobs=n),
        lambda n: advance_poll_lag_diagnoses(
            store, repo, state, agent_binary, max_new_jobs=n),
        lambda n: advance_poll_pairs(store, repo, state, max_new_jobs=n),
        lambda n: advance_determinism(store, repo, state, max_new_jobs=n),
    )
    queued: list[str] = []
    for step in steps:
        queued.extend(step(max_new_jobs - len(queued)))
        if len(queued) >= max_new_jobs:
            return queued
    return queued + _advance_phase9_jobs(
        store, repo, state, agent_binary,
        max_new_jobs=max_new_jobs - len(queued))
