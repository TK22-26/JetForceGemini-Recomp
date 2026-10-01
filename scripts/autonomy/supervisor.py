"""Bounded, restart-aware local Codex worker for the Phase 9+ job ledger.

This is deliberately a candidate producer, not an autonomous merger or a parity
gate. All packets, logs, worktrees, and the SQLite ledger stay in ignored local
storage. A ChatGPT-authenticated ``codex exec`` is the initial agent transport;
no OpenAI API key is required by this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from typing import Any
import zipfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.autonomy.job_store import JobSpec, JobStore, JobStoreError, ID_RE, SHA256_RE
from scripts.autonomy.atomic_file import replace as replace_atomic
from scripts.autonomy.process_guard import (
    WorkerJob, owner_process_dead, real_python_executable,
)
from scripts.compare_phase9_retrace_hashes import compare as compare_retraces


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE = ROOT / "tools" / "private" / "autonomy"
PACKET_SCHEMA = 1
MAX_PROMPT = 20_000
MAX_LOG_BYTES = 32 * 1024 * 1024
MAX_TIMEOUT = 3_600
MAX_PATCH_BYTES = 1_048_576
MAX_UNTRACKED_BYTES = 32 * 1024 * 1024
DEFAULT_MEMORY_BYTES = 8 * 1024 * 1024 * 1024
DEFAULT_CPU_SECONDS = 3_600
PIN_FILES = ("rom", "emulator", "native")
DIAGNOSIS_SCHEMA_FILE = Path(__file__).with_name("diagnosis.schema.json")
BOUNDED_DIAGNOSIS_SCHEMA_FILE = Path(__file__).with_name("diagnosis.bounded-v2.schema.json")
REVIEW_SCHEMA_FILE = Path(__file__).with_name("review.schema.json")
DIAGNOSIS_CLASSES = {"capture_misalignment", "code_divergence",
                     "insufficient_evidence", "other"}
ALIGNMENT_STATES = {"validated", "unvalidated", "contradicted"}
API_KEY_ENV = ("OPENAI_API_KEY", "CODEX_API_KEY", "ANTHROPIC_API_KEY",
               "GEMINI_API_KEY", "GOOGLE_API_KEY")


class SupervisorError(ValueError):
    """A packet or worker precondition was not satisfied."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tool_identity_sha256(agent_binary: Path) -> str:
    """Pin the actual npm Codex runtime, not only its small Windows shim."""
    files = [agent_binary]
    if agent_binary.name.lower() == "codex.cmd":
        package = agent_binary.parent / "node_modules" / "@openai" / "codex"
        launcher = package / "bin" / "codex.js"
        runtime = package / "node_modules" / "@openai" / "codex-win32-x64" / \
            "vendor" / "x86_64-pc-windows-msvc" / "bin" / "codex.exe"
        if not launcher.is_file() or not runtime.is_file():
            raise SupervisorError("cannot locate npm Codex runtime for exact tool pin")
        files.extend((launcher, runtime))
    digest = hashlib.sha256()
    for file in files:
        # Windows path resolution can canonicalize codex.CMD to codex.cmd.
        # Both spellings name the same tool bytes and must have one identity.
        digest.update(file.name.lower().encode("ascii"))
        digest.update(bytes.fromhex(file_sha256(file)))
    return digest.hexdigest()


def no_api_key_env() -> dict[str, str]:
    environment = os.environ.copy()
    for key in API_KEY_ENV:
        environment.pop(key, None)
    return environment


def require_chatgpt_login(agent_binary: Path) -> None:
    result = subprocess.run([str(agent_binary), "login", "status"],
                            capture_output=True, text=True, timeout=15,
                            env=no_api_key_env(), check=False)
    if result.returncode != 0 or "Logged in using ChatGPT" not in (result.stdout + result.stderr):
        raise SupervisorError("Codex CLI is not signed in with ChatGPT")


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def read_diagnosis(path: Path) -> dict[str, Any]:
    """Validate the machine-actionable subset beyond the CLI's JSON Schema."""
    try:
        diagnosis = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SupervisorError("diagnosis output is missing or invalid JSON") from error
    return validate_diagnosis(diagnosis)


def validate_diagnosis(diagnosis: object) -> dict[str, Any]:
    required = {"classification", "alignment", "first_supported_retrace",
                "evidence", "hypothesis", "next_test", "confidence"}
    if not isinstance(diagnosis, dict) or set(diagnosis) != required:
        raise SupervisorError("diagnosis output fields do not match schema")
    if any(not isinstance(diagnosis[key], str) for key in
           ("classification", "alignment", "confidence")) or \
            diagnosis["classification"] not in DIAGNOSIS_CLASSES or \
            diagnosis["alignment"] not in ALIGNMENT_STATES or \
            diagnosis["confidence"] not in {"low", "medium", "high"}:
        raise SupervisorError("diagnosis output has an invalid classification")
    retrace = diagnosis["first_supported_retrace"]
    if retrace is not None and (type(retrace) is not int or retrace < 0):
        raise SupervisorError("diagnosis retrace must be nonnegative or null")
    evidence = diagnosis["evidence"]
    if not isinstance(evidence, list) or len(evidence) > 12 or any(
            not isinstance(item, str) or not 1 <= len(item) <= 500
            for item in evidence):
        raise SupervisorError("diagnosis evidence is invalid")
    if any(not isinstance(diagnosis[key], str) or
           not 1 <= len(diagnosis[key]) <= 1000
           for key in ("hypothesis", "next_test")):
        raise SupervisorError("diagnosis needs a bounded hypothesis and next test")
    if diagnosis["classification"] == "code_divergence" and \
            (diagnosis["alignment"] != "validated" or retrace is None or
             not evidence):
        raise SupervisorError("code divergence requires aligned retrace evidence")
    return diagnosis


def bounded_diagnosis_contract() -> dict[str, Any]:
    return {"version": 2, "sha256": file_sha256(BOUNDED_DIAGNOSIS_SCHEMA_FILE)}


def diagnosis_schema_file(packet: dict[str, Any]) -> Path:
    contract = packet.get("diagnosis_contract")
    if contract is None and "diagnosis_contract" not in packet:
        return DIAGNOSIS_SCHEMA_FILE  # Preserve historical schema identities.
    if (packet.get("kind") != "diagnose" or not isinstance(contract, dict) or
            set(contract) != {"version", "sha256"} or
            type(contract["version"]) is not int or contract["version"] != 2 or
            contract["sha256"] != file_sha256(BOUNDED_DIAGNOSIS_SCHEMA_FILE)):
        raise SupervisorError("diagnosis contract is unsupported or changed")
    return BOUNDED_DIAGNOSIS_SCHEMA_FILE


def validate_diagnosis_format(packet: dict[str, Any], diagnosis: dict[str, Any]) -> None:
    source = packet.get("diagnosis_format_source")
    if source is None:
        return
    path = Path(source["path"])
    if file_sha256(path) != source["sha256"]:
        raise SupervisorError("diagnosis format source changed")
    original = json.loads(path.read_text(encoding="utf-8"))
    if any(diagnosis.get(key) != original.get(key) for key in
           ("classification", "alignment", "first_supported_retrace", "confidence", "evidence")):
        raise SupervisorError("format recovery changed evidence or certainty")


def read_review(path: Path) -> dict[str, Any]:
    try:
        review = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SupervisorError("review output is missing or invalid JSON") from error
    if (not isinstance(review, dict) or
            set(review) != {"verdict", "findings", "confidence"} or
            not isinstance(review["verdict"], str) or
            review["verdict"] not in {"approve", "reject", "needs_evidence"} or
            not isinstance(review["confidence"], str) or
            review["confidence"] not in {"low", "medium", "high"} or
            not isinstance(review["findings"], list) or
            len(review["findings"]) > 12 or
            any(not isinstance(item, str) or not 1 <= len(item) <= 1000
                for item in review["findings"]) or
            (review["verdict"] == "reject" and not review["findings"])):
        raise SupervisorError("review output fields do not match schema")
    return review


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args],
                          text=True, capture_output=True, check=False)


def _git_ok(repo: Path, *args: str) -> str:
    result = _git(repo, *args)
    if result.returncode:
        raise SupervisorError(f"git {args[0]} failed: {result.stderr.strip()[:300]}")
    return result.stdout.strip()


def validate_review_receipts(result: dict, directory: Path) -> None:
    """Legacy reviews lack receipts; new receipts must match the retained logs."""
    if "candidate_retest_evidence" not in result:
        return
    receipts = result["candidate_retest_evidence"]
    checks = result.get("candidate_retest_validation")
    if not isinstance(receipts, list) or not isinstance(checks, list) or len(receipts) != len(checks):
        raise SupervisorError("review validation receipts are incomplete")
    for index, (receipt, check) in enumerate(zip(receipts, checks)):
        if not isinstance(receipt, dict) or receipt.get("check") != check:
            raise SupervisorError("review validation receipt changed its check")
        for stream in ("stdout", "stderr"):
            expected = directory / f"retest-{index}.{stream}"
            entry = receipt.get(stream)
            if (not isinstance(entry, dict) or entry.get("path") != str(expected) or
                    not expected.is_file() or entry.get("sha256") != file_sha256(expected)):
                raise SupervisorError("review validation log receipt changed")


def _inside(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def validate_candidate_build(recipe: object) -> None:
    """Check a declarative, bounded native build recipe without executing it."""
    required = {"baseline_update_id", "configure_argv", "build_argv",
                "executable", "build_inputs", "timeout_seconds"}
    if not isinstance(recipe, dict) or set(recipe) != required:
        raise SupervisorError("candidate build recipe has invalid fields")
    if (not isinstance(recipe["baseline_update_id"], str) or
            not ID_RE.fullmatch(recipe["baseline_update_id"])):
        raise SupervisorError("candidate build needs a baseline update job ID")
    for key in ("configure_argv", "build_argv"):
        argv = recipe[key]
        if (not isinstance(argv, list) or not 2 <= len(argv) <= 40 or
                any(not isinstance(arg, str) or not 1 <= len(arg) <= 512
                    for arg in argv) or
                Path(argv[0]).name.lower() not in ("cmake", "cmake.exe")):
            raise SupervisorError("candidate build commands must be bounded CMake argv")
    if (not any("{source}" in arg for arg in recipe["configure_argv"]) or
            not any("{build}" in arg for arg in recipe["configure_argv"]) or
            not any("{build}" in arg for arg in recipe["build_argv"])):
        raise SupervisorError("candidate build commands need source/build placeholders")
    executable = recipe["executable"]
    if (not isinstance(executable, str) or not 1 <= len(executable) <= 200 or
            "\\" in executable or ":" in executable or executable.startswith("/") or
            any(part in ("", ".", "..") or part.endswith((".", " "))
                for part in executable.split("/"))):
        raise SupervisorError("candidate executable must be relative to private build")
    inputs = recipe["build_inputs"]
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= 32:
        raise SupervisorError("candidate build needs pinned input manifests")
    for item in inputs:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"} or
                not isinstance(item["path"], str) or
                not Path(item["path"]).is_absolute() or
                not isinstance(item["sha256"], str) or
                not SHA256_RE.fullmatch(item["sha256"])):
            raise SupervisorError("candidate build input pin is invalid")
        path = Path(item["path"])
        if not path.is_file() or file_sha256(path) != item["sha256"]:
            raise SupervisorError("candidate build input changed")
    timeout = recipe["timeout_seconds"]
    if type(timeout) is not int or not 60 <= timeout <= 3600:
        raise SupervisorError("candidate build timeout is invalid")


def validate_packet(packet: dict[str, Any], repo: Path) -> None:
    required = {"schema", "job_id", "kind", "source_commit", "pin_files",
                "prompt", "timeout_seconds", "validation", "prerequisites",
                "retry_budget", "allowed_paths", "max_changed_files",
                "evidence_files"}
    optional = {"candidate_build"} if packet.get("kind") == "implement" else set()
    if packet.get("kind") == "diagnose":
        optional.update(("diagnosis_contract", "diagnosis_format_source", "research_completion"))
    if packet.get("kind") in ("plan-experiment", "plan-entry", "plan-point", "plan-interval"):
        optional.add("experiment_contract")
    if not required <= set(packet) or not set(packet) <= required | optional or \
            packet["schema"] != PACKET_SCHEMA:
        raise SupervisorError("packet schema/fields do not match version 1")
    if (not isinstance(packet["job_id"], str) or
            not ID_RE.fullmatch(packet["job_id"])):
        raise SupervisorError("invalid job ID")
    if packet["kind"] not in ("diagnose", "implement", "review", "plan-experiment", "plan-entry", "plan-point", "plan-interval"):
        raise SupervisorError("unsupported agent packet kind")
    if packet["kind"] == "diagnose":
        diagnosis_schema_file(packet)
        if "research_completion" in packet:
            from scripts.autonomy.research_completion import validate_packet as validate_completion
            validate_completion(packet, repo)
    if packet["kind"] in ("plan-experiment", "plan-entry", "plan-point", "plan-interval"):
        experiment_module(packet).validate_contract(packet.get("experiment_contract"))
        if packet["validation"] or packet["allowed_paths"] or packet["max_changed_files"] != 0:
            raise SupervisorError("experiment planners must be read-only without commands")
    if (not isinstance(packet["prompt"], str) or
            not 1 <= len(packet["prompt"]) <= MAX_PROMPT):
        raise SupervisorError("prompt must be 1..20000 characters")
    if (not isinstance(packet["timeout_seconds"], int) or
            isinstance(packet["timeout_seconds"], bool) or
            not 1 <= packet["timeout_seconds"] <= MAX_TIMEOUT):
        raise SupervisorError("timeout_seconds must be 1..3600")
    if (not isinstance(packet["retry_budget"], int) or
            isinstance(packet["retry_budget"], bool) or
            not 0 <= packet["retry_budget"] <= 3):
        raise SupervisorError("retry_budget must be 0..3")
    if (not isinstance(packet["prerequisites"], list) or
            len(packet["prerequisites"]) > 16 or
            any(not isinstance(item, str) or not ID_RE.fullmatch(item)
                for item in packet["prerequisites"])):
        raise SupervisorError("invalid prerequisites")
    if (not isinstance(packet["validation"], list) or
            len(packet["validation"]) > 8 or
            any(not isinstance(cmd, list) or not 1 <= len(cmd) <= 20 or
                any(not isinstance(arg, str) or not 1 <= len(arg) <= 512
                    for arg in cmd) for cmd in packet["validation"])):
        raise SupervisorError("validation must be up to eight argv arrays")
    if packet["kind"] == "implement" and not packet["validation"]:
        raise SupervisorError("implementation packets require validation commands")
    if (not isinstance(packet["allowed_paths"], list) or
            len(packet["allowed_paths"]) > 20 or
            (packet["kind"] == "implement" and not packet["allowed_paths"])):
        raise SupervisorError("implementation packets require allowed_paths")
    for allowed in packet["allowed_paths"]:
        if (not isinstance(allowed, str) or not 1 <= len(allowed) <= 200 or
                "\\" in allowed or allowed.startswith("/") or
                any(part in ("", ".", "..") for part in allowed.rstrip("/").split("/"))):
            raise SupervisorError("allowed_paths must be relative Git paths")
    if (not isinstance(packet["max_changed_files"], int) or
            isinstance(packet["max_changed_files"], bool) or
            not 0 <= packet["max_changed_files"] <= 50):
        raise SupervisorError("max_changed_files must be 0..50")
    if packet["kind"] == "implement" and packet["max_changed_files"] == 0:
        raise SupervisorError("implementation needs a positive file budget")
    if "candidate_build" in packet:
        validate_candidate_build(packet["candidate_build"])
    if not isinstance(packet["source_commit"], str) or len(packet["source_commit"]) not in (40, 64):
        raise SupervisorError("source_commit must be a full Git commit ID")
    if _git_ok(repo, "rev-parse", "--verify", packet["source_commit"] + "^{commit}") != packet["source_commit"]:
        raise SupervisorError("source_commit is not an exact local commit")
    pin_files = packet["pin_files"]
    if not isinstance(pin_files, dict) or set(pin_files) != set(PIN_FILES):
        raise SupervisorError("pin_files must name ROM, emulator, and native files")
    for key in PIN_FILES:
        if (not isinstance(pin_files[key], str) or
                not Path(pin_files[key]).is_absolute() or
                not Path(pin_files[key]).is_file()):
            raise SupervisorError(f"{key} pin file must be an existing absolute path")
    if packet["kind"] == "review" and packet["validation"]:
        raise SupervisorError("review jobs must be read-only with no validation commands")
    if (not isinstance(packet["evidence_files"], list) or
            len(packet["evidence_files"]) > 12):
        raise SupervisorError("evidence_files must be a short list")
    if packet["kind"] == "review" and (
            len(packet["prerequisites"]) != 1 or packet["allowed_paths"] or
            packet["max_changed_files"] != 0 or
            len(packet["evidence_files"]) != 3):
        raise SupervisorError("review requires one candidate and three sealed evidence files")
    for evidence in packet["evidence_files"]:
        if (not isinstance(evidence, dict) or
                set(evidence) != {"path", "sha256"} or
                not isinstance(evidence["path"], str) or
                not Path(evidence["path"]).is_absolute() or
                not isinstance(evidence["sha256"], str) or
                not SHA256_RE.fullmatch(evidence["sha256"])):
            raise SupervisorError("invalid evidence file pin")
        path = Path(evidence["path"])
        if not path.is_file() or file_sha256(path) != evidence["sha256"]:
            raise SupervisorError("evidence file is missing or changed")
        if packet["kind"] == "implement" and path.suffix.lower() == ".json" \
                and path.stat().st_size <= 1_048_576:
            try:
                artifact = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError):
                continue  # A pinned evidence file need not be a JSON object.
            if (isinstance(artifact, dict) and
                    artifact.get("kind") == "jfg-phase9-cpu-rounding-adjudication" and
                    artifact.get("disposition") == "mupen_oracle_semantics_conflict"):
                raise SupervisorError(
                    "implementation cannot use a Mupen CPU semantics conflict "
                    "as repair evidence")
    if "diagnosis_format_source" in packet:
        if ("diagnosis_contract" not in packet or
                packet["diagnosis_format_source"] not in packet["evidence_files"]):
            raise SupervisorError("diagnosis format recovery needs a pinned source and bounded contract")


def experiment_module(packet):
    if packet["kind"] == "plan-interval":
        from scripts.autonomy import interval_plan
        return interval_plan
    if packet["kind"] == "plan-point":
        from scripts.autonomy import point_plan
        return point_plan
    if packet["kind"] == "plan-entry":
        from scripts.autonomy import entry_plan
        return entry_plan
    from scripts.autonomy import experiment_plan
    return experiment_plan


def read_packet(path: Path, repo: Path) -> dict[str, Any]:
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SupervisorError("cannot read packet JSON") from error
    if not isinstance(packet, dict):
        raise SupervisorError("packet must be a JSON object")
    validate_packet(packet, repo)
    return packet


def make_pins(packet: dict[str, Any], agent_binary: Path) -> dict[str, str]:
    return {"source_commit": packet["source_commit"],
            "tool_sha256": tool_identity_sha256(agent_binary),
            **{key + "_sha256": file_sha256(Path(packet["pin_files"][key]))
               for key in PIN_FILES}}


def enqueue_packet(store: JobStore, state: Path, packet: dict[str, Any],
                   agent_binary: Path) -> None:
    state.mkdir(parents=True, exist_ok=True)
    encoded = canonical_bytes(packet)
    digest = hashlib.sha256(encoded).hexdigest()
    packet_dir = state / "packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    target = packet_dir / (packet["job_id"] + ".json")
    if target.exists() and target.read_bytes() != encoded:
        raise SupervisorError("job ID already names a different packet")
    if not target.exists():
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(target)
    pins = make_pins(packet, agent_binary)
    spec = JobSpec(packet["job_id"], pins, ("packet:" + digest,),
                   tuple(packet["prerequisites"]), "source-writer",
                   packet["retry_budget"], "json_complete")
    store.enqueue(spec)


def queue_divergence(store: JobStore, repo: Path, state: Path,
                     agent_binary: Path, *, job_id: str, native_trace: Path,
                     oracle_trace: Path, oracle_offset: int,
                     pin_files: dict[str, str], timeout_seconds: int) -> dict[str, Any]:
    """Turn a pinned trace comparison into a read-only diagnosis job."""
    if not ID_RE.fullmatch(job_id):
        raise SupervisorError("invalid job ID")
    native_trace, oracle_trace = native_trace.resolve(strict=True), oracle_trace.resolve(strict=True)
    report, match = compare_retraces(native_trace, oracle_trace, oracle_offset)
    if match:
        return report
    intake = state / "intake"
    intake.mkdir(parents=True, exist_ok=True)
    report_path = intake / (job_id + "-comparison.json")
    encoded = canonical_bytes(report)
    if report_path.exists() and report_path.read_bytes() != encoded:
        raise SupervisorError("job ID already names a different divergence report")
    if not report_path.exists():
        _write_json_atomic(report_path, report)
    queue_diagnosis_report(
        store, repo, state, agent_binary, job_id=job_id,
        report_path=report_path, report=report,
        native_trace=native_trace, oracle_trace=oracle_trace,
        pin_files=pin_files, timeout_seconds=timeout_seconds,
        source_commit=_git_ok(repo, "rev-parse", "HEAD"), prerequisites=[])
    return report


def queue_diagnosis_report(store: JobStore, repo: Path, state: Path,
                           agent_binary: Path, *, job_id: str,
                           report_path: Path, report: dict[str, Any],
                           native_trace: Path, oracle_trace: Path,
                           pin_files: dict[str, str], timeout_seconds: int,
                           source_commit: str,
                           prerequisites: list[str]) -> None:
    """Queue one immutable read-only diagnosis of a sealed raw comparison."""
    if report.get("match") is not False or report.get("kind") != \
            "jfg-phase9-retrace-comparison" or report.get("schema") != 1:
        raise SupervisorError("diagnosis requires a mismatching comparison report")
    if not ID_RE.fullmatch(job_id):
        raise SupervisorError("invalid diagnosis job ID")
    report_path = report_path.resolve(strict=True)
    native_trace = native_trace.resolve(strict=True)
    oracle_trace = oracle_trace.resolve(strict=True)
    if json.loads(report_path.read_text(encoding="utf-8")) != report:
        raise SupervisorError("comparison report changed before diagnosis queueing")
    evidence = [{"path": str(path), "sha256": file_sha256(path)}
                for path in (native_trace, oracle_trace, report_path)]
    first = report["first_divergence"]
    focus = (f"retrace {first['retrace']}, components {first['components']}"
             if first else "coverage/prefix mismatch without an aligned first divergence")
    packet = {
        "schema": PACKET_SCHEMA, "job_id": job_id, "kind": "diagnose",
        "diagnosis_contract": bounded_diagnosis_contract(),
        "source_commit": source_commit,
        "pin_files": pin_files,
        "prompt": ("Diagnose this Phase 9 native/BizHawk comparison: " + focus +
                   ". First verify controller-poll and retrace alignment; do not infer a "
                   "code defect from unaligned traces. Read the pinned comparison report "
                   f"at {report_path}, native trace {native_trace}, and oracle trace "
                   f"{oracle_trace}. Identify the "
                   "earliest supported cause and a small falsifiable next test. Read only."),
        "timeout_seconds": timeout_seconds,
        "validation": [], "prerequisites": prerequisites, "retry_budget": 0,
        "allowed_paths": [], "max_changed_files": 0,
        "evidence_files": evidence,
    }
    validate_packet(packet, repo)
    enqueue_packet(store, state, packet, agent_binary)


def validate_comparison_packet(packet: dict[str, Any], repo: Path) -> None:
    required = {"schema", "job_id", "source_commit", "pin_files",
                "native_trace", "oracle_trace", "oracle_offset", "timeout_seconds"}
    if not isinstance(packet, dict) or set(packet) != required or packet["schema"] != 1:
        raise SupervisorError("invalid comparison packet schema")
    if not isinstance(packet["job_id"], str) or not ID_RE.fullmatch(packet["job_id"]):
        raise SupervisorError("invalid comparison job ID")
    if (not isinstance(packet["source_commit"], str) or
            _git_ok(repo, "rev-parse", "--verify",
                    packet["source_commit"] + "^{commit}") != packet["source_commit"]):
        raise SupervisorError("comparison source commit is not a local full commit")
    if (type(packet["oracle_offset"]) is not int or
            abs(packet["oracle_offset"]) > 1_000_000):
        raise SupervisorError("invalid oracle retrace offset")
    if (type(packet["timeout_seconds"]) is not int or
            not 1 <= packet["timeout_seconds"] <= MAX_TIMEOUT):
        raise SupervisorError("invalid comparison timeout")
    if not isinstance(packet["pin_files"], dict) or set(packet["pin_files"]) != set(PIN_FILES):
        raise SupervisorError("comparison pin_files are incomplete")
    for key in PIN_FILES:
        path = packet["pin_files"][key]
        if not isinstance(path, str) or not Path(path).is_absolute() or not Path(path).is_file():
            raise SupervisorError(f"comparison {key} pin file is missing")
    for key in ("native_trace", "oracle_trace"):
        item = packet[key]
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"} or
                not isinstance(item["path"], str) or
                not Path(item["path"]).is_absolute() or
                not isinstance(item["sha256"], str) or
                not SHA256_RE.fullmatch(item["sha256"])):
            raise SupervisorError("invalid comparison trace pin")
        path = Path(item["path"])
        if not path.is_file() or file_sha256(path) != item["sha256"]:
            raise SupervisorError("comparison trace changed or disappeared")


def comparison_pins(packet: dict[str, Any], repo: Path) -> dict[str, str]:
    return {"source_commit": packet["source_commit"],
            "tool_sha256": file_sha256(repo / "scripts" / "compare_phase9_retrace_hashes.py"),
            **{key + "_sha256": file_sha256(Path(packet["pin_files"][key]))
               for key in PIN_FILES}}


def queue_comparison(store: JobStore, repo: Path, state: Path, *, job_id: str,
                     native_trace: Path, oracle_trace: Path, oracle_offset: int,
                     pin_files: dict[str, str], timeout_seconds: int) -> None:
    packet = {
        "schema": 1, "job_id": job_id,
        "source_commit": _git_ok(repo, "rev-parse", "HEAD"),
        "pin_files": {key: str(Path(pin_files[key]).resolve(strict=True))
                      for key in PIN_FILES},
        "native_trace": {"path": str(native_trace.resolve(strict=True)),
                         "sha256": file_sha256(native_trace)},
        "oracle_trace": {"path": str(oracle_trace.resolve(strict=True)),
                         "sha256": file_sha256(oracle_trace)},
        "oracle_offset": oracle_offset,
        "timeout_seconds": timeout_seconds,
    }
    validate_comparison_packet(packet, repo)
    state.mkdir(parents=True, exist_ok=True)
    encoded = canonical_bytes(packet)
    digest = hashlib.sha256(encoded).hexdigest()
    packet_dir = state / "comparison-packets"
    packet_dir.mkdir(parents=True, exist_ok=True)
    target = packet_dir / (job_id + ".json")
    if target.exists() and target.read_bytes() != encoded:
        raise SupervisorError("comparison ID already names a different packet")
    if not target.exists():
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(target)
    store.enqueue(JobSpec(job_id, comparison_pins(packet, repo),
                          ("comparison-packet:" + digest,), (),
                          "comparison:phase9", 1, "json_complete"))


def run_comparison_lease(store: JobStore, lease: dict[str, Any],
                         repo: Path, state: Path) -> str:
    job_id, token, attempt = lease["job_id"], lease["token"], lease["attempt"]
    attempt_dir = state / "attempts" / job_id / f"{attempt:04d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    result_file = attempt_dir / "result.json"
    try:
        packet_path = state / "comparison-packets" / (job_id + ".json")
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        validate_comparison_packet(packet, repo)
        digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if lease["spec"]["inputs"] != ["comparison-packet:" + digest]:
            raise SupervisorError("comparison packet changed since enqueue")
        if comparison_pins(packet, repo) != lease["spec"]["pins"]:
            raise SupervisorError("comparison tool or input pin changed")
        for previous in store.attempt_history(job_id):
            if previous["number"] >= attempt or previous["outcome"] != "expired":
                continue
            prior_dir = state / "attempts" / job_id / f"{previous['number']:04d}"
            guarded = list(prior_dir.glob("*.guard.json"))
            if guarded or (prior_dir / "result.json").is_file():
                if not expired_attempt_contained(prior_dir):
                    raise SupervisorError("expired comparison worker may still be alive")
                if recover_complete_result(store, lease, prior_dir, comparison=True):
                    return f"{job_id}: prior comparison recovered"
        store.start(job_id, token)
        report_path = attempt_dir / "comparison.json"
        deadline = time.monotonic() + packet["timeout_seconds"]
        heartbeat = lambda: store.heartbeat(job_id, token, ttl=120)
        command = [real_python_executable(), "-m", "scripts.compare_phase9_retrace_hashes",
                   packet["native_trace"]["path"], packet["oracle_trace"]["path"],
                   "--oracle-offset", str(packet["oracle_offset"]),
                   "--output", str(report_path)]
        code, reason = bounded_command(command, repo,
                                       attempt_dir / "comparator.stdout",
                                       attempt_dir / "comparator.stderr",
                                       deadline, heartbeat, state / "PAUSED",
                                       guard_record=attempt_dir / "comparator.guard.json")
        if code not in (0, 1) or reason or not report_path.is_file():
            raise SupervisorError("comparison did not finish within its contract")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (report.get("kind") != "jfg-phase9-retrace-comparison" or
                report.get("schema") != 1 or report.get("match") is not (code == 0)):
            raise SupervisorError("comparison exit status and report disagree")
        validate_comparison_packet(packet, repo)
        if comparison_pins(packet, repo) != lease["spec"]["pins"]:
            raise SupervisorError("comparison pins changed during execution")
        first = report.get("first_divergence")
        _write_json_atomic(result_file, {
            "schema": 1, "complete": True, "kind": "comparison-execution",
            "job_id": job_id, "attempt": attempt, "packet_sha256": digest,
            "comparison_sha256": file_sha256(report_path),
            "match": report["match"],
            "first_raw_divergence_retrace": first["retrace"] if first else None,
            "alignment_validated": False, "parity_verified": False,
            "pins": lease["spec"]["pins"],
        })
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, result_file)
        store.pass_job(job_id, token)
        return f"{job_id}: raw comparison sealed"
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        _write_json_atomic(result_file, {
            "schema": 1, "complete": False, "kind": "comparison-execution",
            "job_id": job_id, "attempt": attempt,
            "stop_reason": str(error)[:300],
        })
        try:
            store.fail_job(job_id, token, str(error)[:300],
                           blocked=isinstance(error, SupervisorError))
        except JobStoreError:
            pass
        return f"{job_id}: comparison blocked ({error})"


def _terminate_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, check=False)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def bounded_command(argv: list[str], cwd: Path, stdout: Path, stderr: Path,
                    deadline: float, heartbeat: callable,
                    pause_file: Path, stdin_path: Path | None = None,
                    max_output_bytes: int = MAX_LOG_BYTES,
                    memory_limit_bytes: int = DEFAULT_MEMORY_BYTES,
                    cpu_seconds: int = DEFAULT_CPU_SECONDS,
                    guard_record: Path | None = None,
                    minimum_free_bytes: int = 0,
                    output_tree: Path | None = None,
                    max_output_tree_bytes: int | None = None,
                    environment_overrides: dict[str, str] | None = None) -> tuple[int, str | None]:
    """Run one child with wall-time/log caps and periodic lease heartbeats."""
    if (type(minimum_free_bytes) is not int or minimum_free_bytes < 0 or
            (output_tree is None) != (max_output_tree_bytes is None) or
            (max_output_tree_bytes is not None and
             (type(max_output_tree_bytes) is not int or max_output_tree_bytes <= 0))):
        raise ValueError("invalid guarded disk limits")
    if output_tree is not None and not output_tree.resolve().is_relative_to(
            cwd.resolve()):
        raise ValueError("guarded output tree escapes command workspace")
    if environment_overrides is not None and (
            not isinstance(environment_overrides, dict) or
            any(key not in ("JFG_PHASE95_VISUAL_ROOT", "JFG_PHASE95_VISUAL_STATE") or
                not isinstance(value, str) for key, value in
                environment_overrides.items())):
        raise ValueError("invalid guarded environment overrides")
    if minimum_free_bytes and shutil.disk_usage(cwd).free < minimum_free_bytes:
        return -1, "disk reserve"
    heartbeat()  # Check the investigation allowance before starting another process.

    def tree_bytes(path: Path, limit: int) -> int:
        total = 0
        if path.exists():
            for entry in path.rglob("*"):
                if entry.is_symlink():
                    return limit + 1
                if entry.is_file():
                    total += entry.stat().st_size
                    if total > limit:
                        break
        return total

    if guard_record is not None:
        _write_json_atomic(guard_record, {
            "schema": 1, "state": "starting", "owner_pid": os.getpid(),
        })
    with stdout.open("wb") as out, stderr.open("wb") as err, \
            (stdin_path.open("rb") if stdin_path else open(os.devnull, "rb")) as source, \
            WorkerJob(memory_limit_bytes=memory_limit_bytes, cpu_seconds=cpu_seconds) as guard:
        environment = no_api_key_env()
        environment.update(environment_overrides or {})
        process = subprocess.Popen(argv, cwd=str(cwd), stdout=out, stderr=err,
                                   stdin=source, env=environment,
                                   start_new_session=(os.name != "nt"))
        assigned = False
        try:
            guard.assign(process)
            assigned = True
            if guard_record is not None:
                _write_json_atomic(guard_record, {
                    "schema": 1, "state": "guarded", "owner_pid": os.getpid(),
                    "child_pid": process.pid,
                })
            next_heartbeat = time.monotonic() + 1
            next_resource_check = time.monotonic()
            while process.poll() is None:
                reason = None
                if pause_file.exists():
                    reason = "paused"
                elif time.monotonic() >= deadline:
                    reason = "timeout"
                elif stdout.stat().st_size + stderr.stat().st_size > max_output_bytes:
                    reason = "log limit"
                if reason is None and time.monotonic() >= next_resource_check:
                    if minimum_free_bytes and \
                            shutil.disk_usage(cwd).free < minimum_free_bytes:
                        reason = "disk reserve"
                    elif output_tree is not None and tree_bytes(
                            output_tree, max_output_tree_bytes) > max_output_tree_bytes:
                        reason = "output tree limit"
                    next_resource_check = time.monotonic() + 1
                if reason:
                    _terminate_tree(process)
                    return process.returncode or -1, reason
                if time.monotonic() >= next_heartbeat:
                    heartbeat()
                    next_heartbeat = time.monotonic() + 1
                time.sleep(0.2)
        finally:
            _terminate_tree(process)
            if guard_record is not None:
                _write_json_atomic(guard_record, {
                    "schema": 1, "state": "finished" if assigned else "uncertain",
                    "owner_pid": os.getpid(), "child_pid": process.pid,
                })
        if stdout.stat().st_size + stderr.stat().st_size > max_output_bytes:
            return process.returncode, "log limit"
        if minimum_free_bytes and shutil.disk_usage(cwd).free < minimum_free_bytes:
            return process.returncode, "disk reserve"
        if output_tree is not None and tree_bytes(
                output_tree, max_output_tree_bytes) > max_output_tree_bytes:
            return process.returncode, "output tree limit"
        return process.returncode, None


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(canonical_bytes(payload))
    replace_atomic(temporary, path)


def _git_bytes(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args],
                            capture_output=True, check=False)
    if result.returncode:
        raise SupervisorError(f"git {args[0]} failed while collecting candidate")
    return result.stdout


def _git_paths(data: bytes) -> list[str]:
    return [item.decode("utf-8", errors="surrogateescape")
            for item in data.split(b"\0") if item]


def snapshot_candidate(worktree: Path, source_commit: str,
                       attempt_dir: Path, packet: dict[str, Any],
                       deadline: float, heartbeat: callable,
                       pause_file: Path) -> dict[str, Any]:
    """Freeze tracked patch and untracked file contents in private storage."""
    tracked = _git_paths(_git_bytes(worktree, "diff", "--name-only", "-z",
                                    source_commit, "--"))
    untracked = _git_paths(_git_bytes(worktree, "ls-files", "--others",
                                      "--exclude-standard", "-z"))
    paths = sorted(set(tracked + untracked))
    if len(paths) > packet["max_changed_files"]:
        raise SupervisorError("candidate exceeds changed-file budget")
    for path in paths:
        if path.startswith(("corpus/", "roms/", "tools/", "assets/private/")) or \
                path == "docs/planning/JFG_RECOMP_MASTER_PLAN.md":
            raise SupervisorError("candidate touches protected source or golden data")
        if not any(path == allowed.rstrip("/") or
                   path.startswith(allowed.rstrip("/") + "/")
                   for allowed in packet["allowed_paths"]):
            raise SupervisorError("candidate changed a path outside packet scope")
    if packet["kind"] != "implement" and paths:
        raise SupervisorError("read-only agent changed files")
    patch_path = attempt_dir / "tracked.patch"
    code, issue = bounded_command(
        ["git", "-C", str(worktree), "diff", "--binary", source_commit, "--"],
        worktree, patch_path, attempt_dir / "patch.stderr", deadline,
        heartbeat, pause_file, max_output_bytes=MAX_PATCH_BYTES,
        guard_record=attempt_dir / "patch.guard.json")
    if code != 0 or issue:
        raise SupervisorError("cannot capture tracked patch within limits")
    zip_path = attempt_dir / "untracked.zip"
    total = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in untracked:
            target = worktree / path
            if target.is_symlink() or not target.is_file() or not _inside(target, worktree):
                raise SupervisorError("untracked path is unsafe or not a regular file")
            total += target.stat().st_size
            if total > MAX_UNTRACKED_BYTES:
                raise SupervisorError("untracked files exceed private bundle limit")
            archive.write(target, arcname=path)
    return {"changed_paths": paths, "tracked_patch_sha256": file_sha256(patch_path),
            "untracked_zip_sha256": file_sha256(zip_path)}


def expired_attempt_contained(attempt_dir: Path) -> bool:
    """Prove all recorded children were guarded and their owner has exited."""
    records = sorted(attempt_dir.glob("*.guard.json"))
    if not records:
        return False
    for path in records:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if (record.get("schema") != 1 or
                record.get("state") not in ("guarded", "finished") or
                not owner_process_dead(record.get("owner_pid"))):
            return False
    return True


def recover_complete_result(store: JobStore, lease: dict[str, Any],
                            prior_dir: Path, *, comparison: bool,
                            expected_validation: list[list[str]] | None = None,
                            expected_retest_validation: list[list[str]] | None = None,
                            expected_diagnosis_schema: Path = DIAGNOSIS_SCHEMA_FILE,
                            diagnosis_packet: dict[str, Any] | None = None,
                            experiment_packet: dict[str, Any] | None = None,
                            implement: bool = False,
                            diagnose: bool = False,
                            review: bool = False) -> bool:
    """Seal a verified complete result after a crash without rerunning work."""
    path = prior_dir / "result.json"
    if not path.is_file():
        return False
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or result.get("complete") is not True:
        return False
    expected_packet = lease["spec"]["inputs"][0].split(":", 1)[1]
    if (result.get("job_id") != lease["job_id"] or
            result.get("packet_sha256") != expected_packet or
            result.get("pins") != lease["spec"]["pins"]):
        raise SupervisorError("expired complete result has inconsistent identity")
    if comparison:
        report = prior_dir / "comparison.json"
        report_payload = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
        if (result.get("kind") != "comparison-execution" or
                not report.is_file() or
                result.get("comparison_sha256") != file_sha256(report) or
                report_payload.get("kind") != "jfg-phase9-retrace-comparison" or
                result.get("match") is not report_payload.get("match") or
                result.get("alignment_validated") is not False or
                result.get("parity_verified") is not False):
            raise SupervisorError("expired comparison result bundle is incomplete")
    else:
        tracked, untracked = prior_dir / "tracked.patch", prior_dir / "untracked.zip"
        checks = result.get("validation")
        if (result.get("agent_exit_code") != 0 or result.get("stop_reason") is not None or
                result.get("candidate_only") is not True or
                result.get("source_commit") != lease["spec"]["pins"]["source_commit"] or
                not tracked.is_file() or not untracked.is_file() or
                result.get("tracked_patch_sha256") != file_sha256(tracked) or
                result.get("untracked_zip_sha256") != file_sha256(untracked) or
                not isinstance(checks, list) or len(checks) != len(expected_validation or []) or
                any(check.get("argv") != argv or check.get("exit_code") != 0 or
                    check.get("stop_reason") for check, argv in
                    zip(checks, expected_validation or [])) or
                (implement and not result.get("changed_paths")) or
                result.get("requires_independent_review") is not implement):
            raise SupervisorError("expired agent candidate bundle is incomplete")
        if diagnose:
            diagnosis_path = prior_dir / "last-message.txt"
            diagnosis = read_diagnosis(diagnosis_path)
            if diagnosis_packet is not None:
                validate_diagnosis_format(diagnosis_packet, diagnosis)
                from scripts.autonomy.research_completion import validate_output
                validate_output(diagnosis_packet, prior_dir, diagnosis, result)
            if (result.get("diagnosis_sha256") != file_sha256(diagnosis_path) or
                    result.get("diagnosis_schema_sha256") !=
                    file_sha256(expected_diagnosis_schema)):
                raise SupervisorError("expired diagnosis output changed")
        if experiment_packet is not None:
            module = experiment_module(experiment_packet)
            proposal = prior_dir / "last-message.txt"
            module.read(proposal, experiment_packet["experiment_contract"])
            if (result.get("experiment_plan_sha256") != file_sha256(proposal) or
                    result.get("experiment_schema_sha256") != file_sha256(module.SCHEMA_FILE)):
                raise SupervisorError("expired experiment plan changed")
        if review:
            review_path = prior_dir / "last-message.txt"
            read_review(review_path)
            retest = result.get("candidate_retest_validation")
            if (result.get("review_sha256") != file_sha256(review_path) or
                    result.get("review_schema_sha256") !=
                    file_sha256(REVIEW_SCHEMA_FILE) or
                    not isinstance(result.get("candidate_commit"), str) or
                    not SHA256_RE.fullmatch(result.get("candidate_result_sha256", "")) or
                    not isinstance(retest, list) or
                    len(retest) != len(expected_retest_validation or []) or
                    any(not isinstance(check, dict) or
                        check.get("argv") != argv or
                        check.get("exit_code") != 0 or
                        check.get("stop_reason") is not None
                        for check, argv in zip(
                            retest, expected_retest_validation or []))):
                raise SupervisorError("expired review output changed")
            validate_review_receipts(result, prior_dir)
    store.start(lease["job_id"], lease["token"])
    store.verify(lease["job_id"], lease["token"])
    store.seal_artifact(lease["job_id"], lease["token"], path)
    store.pass_job(lease["job_id"], lease["token"])
    return True


def run_once(repo: Path, state: Path, agent_binary: Path, **options) -> str:
    """Apply project-wide investigation accounting around every job lane."""
    from scripts.autonomy import progress_guard
    if (state / "PAUSED").exists():
        return "paused"
    with JobStore(state / "jobs.sqlite") as store:
        store.reclaim_expired()
        progress_guard.reconcile(store, repo, state)
    try:
        outcome = _run_once(repo, state, agent_binary, **options)
    finally:
        with JobStore(state / "jobs.sqlite") as store:
            progress_guard.reconcile(store, repo, state)
            if progress_guard.enabled(store.connection):
                _write_json_atomic(state / "investigation-progress.json", progress_guard.status(store))
    with JobStore(state / "jobs.sqlite") as store:
        if outcome == "idle" and progress_guard.halted(store):
            return "progress-stopped: no runnable admitted investigation; see investigation-progress.json"
    return outcome


def _run_once(repo: Path, state: Path, agent_binary: Path,
             *, agent_prefix: list[str] | None = None,
             require_auth: bool = True,
             allow_agent: bool = True,
             job_id: str | None = None) -> str:
    """Execute at most one queued job. Return a short redacted outcome."""
    if (state / "PAUSED").exists():
        return "paused"
    with JobStore(state / "jobs.sqlite") as store:
        store.reclaim_expired()
        if job_id is not None:
            named = store.job(job_id)
            # An invocation using the wrong installed launcher is not a worker
            # attempt. Check before leasing; retain the normal post-lease check
            # as well so changes between these reads still fail closed.
            if named["state"] == "queued" and named["spec"]["inputs"][0].startswith("packet:"):
                named_packet = read_packet(state / "packets" / (job_id + ".json"), repo)
                if make_pins(named_packet, agent_binary) != named["spec"]["pins"]:
                    raise SupervisorError("named worker tool or input pins differ; job remains queued")
            if (not allow_agent and named["spec"]["inputs"] and
                    named["spec"]["inputs"][0].startswith("packet:")):
                raise SupervisorError("agent job is disabled by the current cap")
            lease = store.lease_job(job_id, "local-supervisor", ttl=120)
            if lease is None:
                denial = store.connection.execute(
                    "SELECT reason FROM guard_denials WHERE job_id=?", (job_id,)).fetchone()
                if denial and named["state"] == "queued":
                    return f"progress-stopped: {job_id}: {denial['reason']}"
                raise SupervisorError(f"named job is not queued or its prerequisites are unavailable: {job_id}")
        else:
            lease = store.lease_next("local-supervisor", ttl=120,
                                     agent_jobs=allow_agent,
                                     priority_resources=("analysis:poll-lag",))
        if lease is None:
            return "idle"
        if lease["spec"]["inputs"][0].startswith("comparison-packet:"):
            return run_comparison_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("alignment-packet:"):
            from scripts.autonomy.alignment_job import run_alignment_lease
            return run_alignment_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("update-packet:"):
            from scripts.autonomy.update_job import run_update_lease
            return run_update_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("word-experiment:"):
            from scripts.autonomy.state_word_experiment import run_lease
            return run_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("entry-experiment:"):
            from scripts.autonomy.entry_experiment import run_lease
            return run_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("interval-experiment:"):
            from scripts.autonomy.interval_experiment import run_lease
            return run_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("device-experiment:"):
            from scripts.autonomy.device_experiment import run_lease
            return run_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("count-ledger-experiment:"):
            from scripts.autonomy.count_ledger_experiment import run_lease
            return run_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("instruction-observation:"):
            from scripts.autonomy.instruction_job import run_lease
            return run_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("instruction-capture:"):
            from scripts.autonomy.instruction_capture import run_lease
            return run_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("point-experiment:"):
            from scripts.autonomy.point_experiment import run_lease
            return run_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("vi-boundary-packet:"):
            from scripts.autonomy.vi_boundary_job import run_boundary_lease
            return run_boundary_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("candidate-retest-packet:"):
            from scripts.autonomy.candidate_native_retest import run_retest_lease
            return run_retest_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("determinism-packet:"):
            from scripts.autonomy.determinism_job import run_determinism_lease
            return run_determinism_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("frontier-cycle-packet:"):
            from scripts.autonomy.frontier_cycle_job import run_lease
            return run_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("poll-pair-packet:"):
            from scripts.autonomy.poll_pair_job import run_lease
            return run_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("poll-lag-packet:"):
            from scripts.autonomy.poll_lag_job import run_lease
            return run_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("event-pair-packet:"):
            from scripts.autonomy.event_pair_job import run_lease
            return run_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("input-focus-packet:"):
            from scripts.autonomy.input_focus_job import run_lease
            return run_lease(store, lease, repo, state)
        if lease["spec"]["inputs"][0].startswith("controller-return-packet:"):
            from scripts.autonomy.controller_return_job import run_lease
            return run_lease(store, lease, repo, state)
        job_id, token = lease["job_id"], lease["token"]
        attempt = lease["attempt"]
        attempt_dir = state / "attempts" / job_id / f"{attempt:04d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        result_file = attempt_dir / "result.json"
        worktree = state / "worktrees" / job_id / f"{attempt:04d}"
        try:
            packet_path = state / "packets" / (job_id + ".json")
            packet = read_packet(packet_path, repo)
            if packet["kind"] == "plan-point":
                from scripts.autonomy.point_prompt import validate_recovery
                validate_recovery(store, repo, state, packet)
            digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
            if lease["spec"]["inputs"] != ["packet:" + digest]:
                raise SupervisorError("packet changed since enqueue")
            if make_pins(packet, agent_binary) != lease["spec"]["pins"]:
                raise SupervisorError("tool or input pins changed since enqueue")
            expected_retest_validation = None
            if packet["kind"] == "review":
                from scripts.autonomy.candidate_review import sealed_candidate
                implementation_packet, _, _ = sealed_candidate(
                    store, repo, state, packet["prerequisites"][0])
                expected_retest_validation = implementation_packet["validation"]
            for previous in store.attempt_history(job_id):
                prior_worktree = state / "worktrees" / job_id / f"{previous['number']:04d}"
                if previous["number"] < attempt and previous["outcome"] == "expired" \
                        and prior_worktree.exists():
                    prior_dir = state / "attempts" / job_id / f"{previous['number']:04d}"
                    if not expired_attempt_contained(prior_dir):
                        raise SupervisorError(
                            "expired prior worktree may still have a live writer; manual recovery needed")
                    if recover_complete_result(store, lease, prior_dir,
                                               comparison=False,
                                               expected_validation=packet["validation"],
                                               expected_retest_validation=expected_retest_validation,
                                               expected_diagnosis_schema=diagnosis_schema_file(packet),
                                               diagnosis_packet=packet,
                                               experiment_packet=packet if packet["kind"] in ("plan-experiment", "plan-entry", "plan-point", "plan-interval") else None,
                                               implement=packet["kind"] == "implement",
                                               diagnose=packet["kind"] == "diagnose",
                                               review=packet["kind"] == "review"):
                        return f"{job_id}: prior candidate recovered"
            if require_auth:
                require_chatgpt_login(agent_binary)
            if worktree.exists():
                raise SupervisorError("attempt worktree already exists; manual recovery needed")
            worktree.parent.mkdir(parents=True, exist_ok=True)
            _git_ok(repo, "worktree", "add", "--detach", str(worktree),
                    packet["source_commit"])
            if not _inside(worktree, state):
                raise SupervisorError("worktree escaped private state directory")
            candidate_commit = None
            candidate_result_sha256 = None
            if packet["kind"] == "review":
                from scripts.autonomy.candidate_review import materialize_review_candidate
                candidate_commit, candidate_result_sha256 = materialize_review_candidate(
                    worktree, packet, store, repo, state)
            store.start(job_id, token)
            deadline = time.monotonic() + packet["timeout_seconds"]
            heartbeat = lambda: store.heartbeat(job_id, token, ttl=120)
            retest_checks = []
            retest_evidence = []
            retest_reason = None
            if packet["kind"] == "review":
                for index, args in enumerate(expected_retest_validation or []):
                    rc, issue = bounded_command(
                        args, worktree,
                        attempt_dir / f"retest-{index}.stdout",
                        attempt_dir / f"retest-{index}.stderr",
                        deadline, heartbeat, state / "PAUSED",
                        guard_record=attempt_dir / f"retest-{index}.guard.json")
                    retest_checks.append({"argv": args, "exit_code": rc,
                                          "stop_reason": issue})
                    if rc != 0 or issue:
                        retest_reason = issue or "candidate retest failed"
                        break
                    retest_evidence.append({
                        "check": retest_checks[-1],
                        **{stream: {"path": str(attempt_dir / f"retest-{index}.{stream}"),
                                    "sha256": file_sha256(attempt_dir / f"retest-{index}.{stream}")}
                           for stream in ("stdout", "stderr")},
                    })
                if retest_reason is None:
                    snapshot_candidate(worktree, candidate_commit, attempt_dir,
                                       packet, deadline, heartbeat, state / "PAUSED")
            prompt = (packet["prompt"] + "\n\nWork only in this isolated worktree. "
                      "Do not push, merge, modify goldens, or claim parity. "
                      "Do not change native CPU semantics solely to follow an "
                      "emulator result contradicted by a pinned independent "
                      "CPU test and processor specification. "
                      "Stop and report if evidence is missing or a gate needs approval.")
            prompt_file = attempt_dir / "prompt.txt"
            prompt_file.write_text(prompt, encoding="utf-8")
            command = list(agent_prefix or [str(agent_binary)]) + [
                "exec", "--json", "-C", str(worktree), "-s",
                "workspace-write" if packet["kind"] == "implement" else "read-only",
                "-c", 'approval_policy="never"',
                "-c", 'forced_login_method="chatgpt"',
                "--output-last-message", str(attempt_dir / "last-message.txt")]
            if packet["kind"] == "diagnose":
                command.extend(["--output-schema", str(diagnosis_schema_file(packet))])
                prompt += ("\n\nReturn the final answer as JSON matching the supplied schema. "
                           "Classify a code divergence only when input and capture "
                           "alignment are validated. Include a falsifiable next test. "
                           "Hard output limits: at most 12 evidence items, 1-500 characters "
                           "each; hypothesis and next_test must each be 1-1000 characters.")
                prompt_file.write_text(prompt, encoding="utf-8")
            elif packet["kind"] in ("plan-experiment", "plan-entry", "plan-point", "plan-interval"):
                command.extend(["--output-schema", str(experiment_module(packet).SCHEMA_FILE)])
                prompt += ("\n\nReturn only the bounded experiment JSON. Do not execute the "
                           "experiment. No commands or executable paths are allowed in a plan. "
                           "Use needs-instrumentation if the available read-only primitive "
                           "cannot distinguish the hypotheses; never invent an observation.")
                prompt_file.write_text(prompt, encoding="utf-8")
            elif packet["kind"] == "review":
                command.extend(["--output-schema", str(REVIEW_SCHEMA_FILE)])
                prompt += ("\n\nThis detached HEAD is the reconstructed candidate commit "
                           f"{candidate_commit}; its parent is the pinned source commit. "
                           "Return the final answer as JSON matching the supplied schema. "
                           "An approve verdict is advisory and does not authorize merge, "
                           "release, or a parity claim.")
                prompt += (
                    "\n\nThe supervisor has already run the declared validation against "
                    "this reconstructed candidate, outside the read-only reviewer sandbox. "
                    "Inspect these exact result/log receipts as evidence; you do not need "
                    "to re-execute them to assess their recorded result. If the receipts "
                    "do not establish a required property, report that gap. These checks "
                    "do not establish untested gameplay parity. Supervisor validation receipts:\n" +
                    json.dumps(retest_evidence, sort_keys=True))
                prompt_file.write_text(prompt, encoding="utf-8")
            command.append("-")
            if retest_reason is None:
                code, reason = bounded_command(
                    command, worktree, attempt_dir / "agent.jsonl",
                    attempt_dir / "agent.stderr", deadline, heartbeat,
                    state / "PAUSED", prompt_file,
                    guard_record=attempt_dir / "agent.guard.json")
            else:
                code, reason = -1, retest_reason
            checks = []
            if code == 0 and reason is None:
                for index, args in enumerate(packet["validation"]):
                    rc, issue = bounded_command(args, worktree,
                                                attempt_dir / f"check-{index}.stdout",
                                                attempt_dir / f"check-{index}.stderr",
                                                deadline, heartbeat, state / "PAUSED",
                                                guard_record=attempt_dir /
                                                f"check-{index}.guard.json")
                    checks.append({"argv": args, "exit_code": rc, "stop_reason": issue})
                    if rc != 0 or issue:
                        reason = issue or "validation failed"
                        break
            if code != 0 and reason is None:
                reason = "agent exited nonzero"
            diagnosis_sha256 = None
            research_completion_trace_sha256 = None
            experiment_sha256 = None
            review_sha256 = None
            if code == 0 and reason is None and packet["kind"] == "diagnose":
                diagnosis_path = attempt_dir / "last-message.txt"
                validate_diagnosis_format(packet, read_diagnosis(diagnosis_path))
                from scripts.autonomy.research_completion import validate_output
                research_completion_trace_sha256 = validate_output(packet, attempt_dir, read_diagnosis(diagnosis_path))
                diagnosis_sha256 = file_sha256(diagnosis_path)
            if code == 0 and reason is None and packet["kind"] in ("plan-experiment", "plan-entry", "plan-point", "plan-interval"):
                proposal = attempt_dir / "last-message.txt"
                experiment_module(packet).read(proposal, packet["experiment_contract"])
                experiment_sha256 = file_sha256(proposal)
            if code == 0 and reason is None and packet["kind"] == "review":
                review_path = attempt_dir / "last-message.txt"
                read_review(review_path)
                review_sha256 = file_sha256(review_path)
            snapshot = {}
            snapshot_error = None
            if reason is not None and time.monotonic() >= deadline:
                # The child has already been contained. Do not launch another
                # process against an expired budget or hide the original stop.
                # Its worktree/logs remain available, but no candidate is sealed.
                snapshot_error = "attempt deadline exhausted; candidate snapshot not attempted"
            else:
                try:
                    snapshot = snapshot_candidate(worktree, candidate_commit or packet["source_commit"],
                                                  attempt_dir, packet, deadline, heartbeat,
                                                  state / "PAUSED")
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    if reason is None:
                        raise
                    snapshot_error = str(error)[:300]
            if make_pins(packet, agent_binary) != lease["spec"]["pins"]:
                raise SupervisorError("tool or input pins changed during attempt")
            if packet["kind"] == "review" and retest_reason is None:
                validate_review_receipts({"candidate_retest_validation": retest_checks,
                                         "candidate_retest_evidence": retest_evidence}, attempt_dir)
            complete = reason is None and (packet["kind"] != "implement" or
                                           bool(snapshot["changed_paths"]))
            if not complete and reason is None:
                reason = "implementation produced no changes"
            _write_json_atomic(result_file, {
                "schema": 1, "complete": complete,
                "candidate_only": True, "job_id": job_id, "attempt": attempt,
                "source_commit": packet["source_commit"],
                "packet_sha256": digest, "pins": lease["spec"]["pins"],
                "worktree": str(worktree), "agent_exit_code": code,
                "stop_reason": reason, "validation": checks,
                "diagnosis_sha256": diagnosis_sha256,
                **({"research_completion_trace_sha256": research_completion_trace_sha256}
                   if research_completion_trace_sha256 else {}),
                "experiment_plan_sha256": experiment_sha256,
                "experiment_schema_sha256": packet.get("experiment_contract", {}).get("schema_sha256"),
                "diagnosis_schema_sha256": (file_sha256(diagnosis_schema_file(packet))
                                            if packet["kind"] == "diagnose" else None),
                "review_sha256": review_sha256,
                "review_schema_sha256": (file_sha256(REVIEW_SCHEMA_FILE)
                                          if packet["kind"] == "review" else None),
                "candidate_commit": candidate_commit,
                "candidate_result_sha256": candidate_result_sha256,
                "candidate_retest_validation": retest_checks,
                "candidate_retest_evidence": retest_evidence,
                **snapshot,
                **({"candidate_snapshot_error": snapshot_error} if snapshot_error else {}),
                "requires_independent_review": packet["kind"] == "implement",
            })
            if complete:
                store.verify(job_id, token)
                store.seal_artifact(job_id, token, result_file)
                store.pass_job(job_id, token)
                return f"{job_id}: candidate sealed"
            store.fail_job(job_id, token, reason or "incomplete")
            return f"{job_id}: failed ({reason})"
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            _write_json_atomic(result_file, {
                "schema": 1, "complete": False, "candidate_only": True,
                "job_id": job_id, "attempt": attempt,
                "stop_reason": str(error)[:300],
            })
            try:
                store.fail_job(job_id, token, str(error)[:300],
                               blocked=isinstance(error, SupervisorError))
            except JobStoreError:
                pass
            return f"{job_id}: blocked ({error})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--codex-bin", type=Path,
                        default=Path(shutil.which("codex") or "codex"))
    commands = parser.add_subparsers(dest="command", required=True)
    queue = commands.add_parser("queue", help="pin and queue a private packet")
    queue.add_argument("packet", type=Path)
    run = commands.add_parser("run-once", help="run at most one bounded job")
    run.add_argument("--execute", action="store_true", help="actually launch Codex")
    run.add_argument("--job-id", help="lease this queued job exactly; fail if unavailable")
    advance = commands.add_parser("advance", help="queue bounded follow-ups from sealed evidence")
    advance.add_argument("--max-new-jobs", type=int, default=1)
    drive = commands.add_parser("drive", help="advance and run a bounded number of jobs")
    drive.add_argument("--execute", action="store_true", help="actually launch workers")
    drive.add_argument("--max-jobs", type=int, default=1)
    serve_command = commands.add_parser("serve", help="opt-in continuous local worker")
    serve_command.add_argument("--execute", action="store_true",
                               help="explicitly allow queued jobs to run")
    serve_command.add_argument("--poll-seconds", type=float, default=15)
    serve_command.add_argument("--max-cycles", type=int)
    serve_command.add_argument("--max-agent-attempts-per-day", type=int, default=4)
    serve_command.add_argument("--audit-seconds", type=float, default=86_400)
    commands.add_parser("audit", help="verify ledger seals and resource locks")
    commands.add_parser("status", help="redacted queue status")
    commands.add_parser("pause", help="prevent new jobs and stop active child")
    commands.add_parser("resume", help="allow explicit run commands again")
    retry = commands.add_parser("retry", help="requeue one failed attempt within its budget")
    retry.add_argument("job_id")
    intake = commands.add_parser("queue-divergence",
                                 help="compare traces and queue read-only Phase 9 diagnosis")
    intake.add_argument("job_id")
    intake.add_argument("native_trace", type=Path)
    intake.add_argument("oracle_trace", type=Path)
    intake.add_argument("--oracle-offset", type=int, default=0)
    intake.add_argument("--rom", type=Path, required=True)
    intake.add_argument("--emulator", type=Path, required=True)
    intake.add_argument("--native", type=Path, required=True)
    intake.add_argument("--timeout-seconds", type=int, default=900)
    comparison = commands.add_parser("queue-comparison",
                                     help="queue bounded deterministic retrace comparison")
    comparison.add_argument("job_id")
    comparison.add_argument("native_trace", type=Path)
    comparison.add_argument("oracle_trace", type=Path)
    comparison.add_argument("--oracle-offset", type=int, default=0)
    comparison.add_argument("--rom", type=Path, required=True)
    comparison.add_argument("--emulator", type=Path, required=True)
    comparison.add_argument("--native", type=Path, required=True)
    comparison.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args(argv)
    repo, state = args.repo.resolve(), args.state.resolve()
    try:
        if not _inside(state, repo / "tools" / "private"):
            raise SupervisorError("state must stay under repo/tools/private")
        if args.command == "queue":
            packet = read_packet(args.packet, repo)
            with JobStore(state / "jobs.sqlite") as store:
                enqueue_packet(store, state, packet, args.codex_bin.resolve(strict=True))
            print(f"queued {packet['job_id']}")
        elif args.command == "status":
            with JobStore(state / "jobs.sqlite") as store:
                print(json.dumps(store.status_projection(), indent=2))
        elif args.command == "pause":
            state.mkdir(parents=True, exist_ok=True)
            (state / "PAUSED").write_text("Paused by user.\n", encoding="utf-8")
            print("paused")
        elif args.command == "resume":
            (state / "PAUSED").unlink(missing_ok=True)
            print("ready; no worker started")
        elif args.command == "retry":
            with JobStore(state / "jobs.sqlite") as store:
                store.retry_failed(args.job_id)
            print(f"requeued {args.job_id}")
        elif args.command == "queue-divergence":
            pins = {"rom": str(args.rom.resolve(strict=True)),
                    "emulator": str(args.emulator.resolve(strict=True)),
                    "native": str(args.native.resolve(strict=True))}
            with JobStore(state / "jobs.sqlite") as store:
                report = queue_divergence(
                    store, repo, state, args.codex_bin.resolve(strict=True),
                    job_id=args.job_id, native_trace=args.native_trace,
                    oracle_trace=args.oracle_trace, oracle_offset=args.oracle_offset,
                    pin_files=pins, timeout_seconds=args.timeout_seconds)
            print("traces match" if report["match"] else
                  f"queued read-only diagnosis {args.job_id}")
        elif args.command == "queue-comparison":
            pins = {"rom": str(args.rom.resolve(strict=True)),
                    "emulator": str(args.emulator.resolve(strict=True)),
                    "native": str(args.native.resolve(strict=True))}
            with JobStore(state / "jobs.sqlite") as store:
                queue_comparison(store, repo, state, job_id=args.job_id,
                                 native_trace=args.native_trace,
                                 oracle_trace=args.oracle_trace,
                                 oracle_offset=args.oracle_offset,
                                 pin_files=pins, timeout_seconds=args.timeout_seconds)
            print(f"queued deterministic comparison {args.job_id}")
        elif args.command == "run-once":
            if not args.execute:
                raise SupervisorError("run-once requires --execute")
            agent_binary = args.codex_bin.resolve(strict=True)
            print(run_once(repo, state, agent_binary, job_id=args.job_id))
        elif args.command == "advance":
            from scripts.autonomy.scheduler import advance_jobs
            with JobStore(state / "jobs.sqlite") as store:
                queued = advance_jobs(
                    store, repo, state, args.codex_bin.resolve(strict=True),
                    max_new_jobs=args.max_new_jobs)
            print(json.dumps({"queued": queued}))
        elif args.command == "drive":
            if not args.execute or not 1 <= args.max_jobs <= 16:
                raise SupervisorError("drive requires --execute and max-jobs 1..16")
            from scripts.autonomy.scheduler import advance_jobs
            agent_binary = args.codex_bin.resolve(strict=True)
            for _ in range(args.max_jobs):
                with JobStore(state / "jobs.sqlite") as store:
                    advance_jobs(store, repo, state, agent_binary)
                outcome = run_once(repo, state, agent_binary)
                print(outcome)
                if outcome in ("paused", "idle"):
                    break
        elif args.command == "audit":
            from scripts.autonomy.continuous import audit_state, write_audit
            with JobStore(state / "jobs.sqlite") as store:
                report = audit_state(store, state)
            path = write_audit(state, report)
            print(json.dumps({"healthy": report["healthy"],
                              "job_count": report["job_count"],
                              "passed_verified": report["passed_verified"],
                              "issue_count": len(report["issues"]),
                              "unresolved_count": len(report["unresolved_jobs"]),
                              "audit": str(path)}))
            if not report["healthy"]:
                return 2
        elif args.command == "serve":
            if not args.execute:
                raise SupervisorError("serve requires --execute")
            from scripts.autonomy.continuous import serve
            serve(repo, state, args.codex_bin.resolve(strict=True),
                  poll_seconds=args.poll_seconds,
                  max_cycles=args.max_cycles,
                  max_agent_attempts_per_utc_day=
                      args.max_agent_attempts_per_day,
                  audit_seconds=args.audit_seconds,
                  on_cycle=lambda event: print(json.dumps(event), flush=True))
    except (SupervisorError, JobStoreError, OSError) as error:
        print(f"supervisor: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
