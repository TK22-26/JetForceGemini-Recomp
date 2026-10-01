"""Opt-in, bounded BizHawk frontier steps in the durable local job ledger.

An objective can end blocked without failing the *worker*: preserving a truthful
bounded result is progress. This module never claims native parity or installs a
startup service. The registration file is private and explicit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from scripts.autonomy.job_store import JobSpec, JobStore, JobStoreError
from scripts.autonomy.process_guard import real_python_executable
from scripts.autonomy.supervisor import (
    SupervisorError, _git_ok, _inside, _write_json_atomic, bounded_command,
    canonical_bytes, expired_attempt_contained, file_sha256,
)
from scripts.phase95_frontier_cycle import load_state, resolve_pointer
from scripts.phase95_frontier_graph import FrontierGraph
from scripts.phase95_frontier_job import select
from scripts.phase95_planner_pin import SOURCES, source_pin


REGISTRATION = "frontier-registration.json"
PREFIX = "frontier-cycle-packet:"
TOOL_FILES = (
    "scripts/autonomy/atomic_file.py",
    "scripts/autonomy/frontier_cycle_job.py",
    "scripts/autonomy/supervisor.py",
    "scripts/autonomy/process_guard.py",
)
MIN_FREE_BYTES = 50 * 1024 * 1024 * 1024
MAX_STEP_BYTES = 4 * 1024 * 1024 * 1024


def _private(repo: Path) -> Path:
    return (repo / "tools" / "private").resolve()


def tool_sha256(repo: Path) -> str:
    planner = source_pin(repo / "scripts" / name for name in SOURCES)
    entries = {"planner": planner["sha256"]}
    entries.update({name: file_sha256(repo / name) for name in TOOL_FILES})
    return hashlib.sha256(canonical_bytes(entries)).hexdigest()


def register(repo: Path, state: Path, cycle_root: Path, emulator: Path,
             rom: Path, script: Path, rom_sha256: str) -> dict:
    repo, state, cycle_root = repo.resolve(), state.resolve(), cycle_root.resolve()
    emulator, rom, script = emulator.resolve(), rom.resolve(), script.resolve()
    if not _inside(state, _private(repo)) or not _inside(cycle_root, _private(repo)):
        raise SupervisorError("frontier registration and cycle must be private")
    if not all(path.is_file() for path in (emulator, rom, script)) or \
            file_sha256(rom) != rom_sha256:
        raise SupervisorError("frontier registration binary or ROM pin mismatch")
    load_state(cycle_root / "state.json", _private(repo))
    payload = {"kind": "jfg-autonomy-frontier-registration", "schema": 1,
               "cycle_root": str(cycle_root), "emulator": str(emulator),
               "rom": str(rom), "rom_sha256": rom_sha256,
               "script": str(script), "script_sha256": file_sha256(script)}
    state.mkdir(parents=True, exist_ok=True)
    path = state / REGISTRATION
    if path.exists() and json.loads(path.read_text()) != payload:
        raise SupervisorError("frontier registration already names different pins")
    if not path.exists():
        _write_json_atomic(path, payload)
    return payload


def registration(repo: Path, state: Path) -> dict | None:
    path = state / REGISTRATION
    if not path.is_file():
        return None
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or set(data) != {
            "kind", "schema", "cycle_root", "emulator", "rom", "rom_sha256",
            "script", "script_sha256"} or \
            data["kind"] != "jfg-autonomy-frontier-registration" or data["schema"] != 1:
        raise SupervisorError("invalid frontier registration")
    cycle_root = Path(data["cycle_root"])
    if not cycle_root.is_absolute() or not _inside(cycle_root, _private(repo)) or \
            not _inside(state, _private(repo)):
        raise SupervisorError("frontier registration escapes private storage")
    for key, digest_key in (("emulator", None), ("rom", "rom_sha256"),
                            ("script", "script_sha256")):
        path = Path(data[key])
        if not path.is_absolute() or not path.is_file() or \
                digest_key is not None and file_sha256(path) != data[digest_key]:
            raise SupervisorError(f"frontier registration {key} pin changed")
    return data


def _cycle(repo: Path, data: dict) -> tuple[Path, dict]:
    root = Path(data["cycle_root"])
    return root, load_state(root / "state.json", _private(repo))


def _native_pin(cycle: dict) -> str:
    verification = cycle.get("verification")
    if verification is None:
        return "0" * 64
    binary = Path(verification["executable"])
    if not binary.is_file() or file_sha256(binary) != verification["executable_sha256"]:
        raise SupervisorError("frontier native diagnostic executable pin changed")
    return verification["executable_sha256"]


def pins(repo: Path, packet: dict) -> dict[str, str]:
    return {"source_commit": packet["source_commit"],
            "tool_sha256": tool_sha256(repo),
            "rom_sha256": file_sha256(Path(packet["rom"])),
            "emulator_sha256": file_sha256(Path(packet["emulator"])),
            "native_sha256": packet["native_sha256"]}


def _packet_path(state: Path, job_id: str) -> Path:
    return state / "frontier-packets" / (job_id + ".json")


def queue_next(store: JobStore, repo: Path, state: Path) -> str | None:
    data = registration(repo, state)
    if data is None or (state / "PAUSED").exists():
        return None
    if shutil.disk_usage(state).free < MIN_FREE_BYTES:
        raise SupervisorError("frontier disk reserve is below 50 GiB")
    root, cycle = _cycle(repo, data)
    if cycle.get("status") == "frontier_exhausted":
        return None
    graph_path = resolve_pointer(cycle["graph"], _private(repo),
                                 cycle["graph_sha256"])
    maintenance = any(cycle.get(name) is not None for name in (
        "pending_node_verification", "pending_export", "pending_verification",
        "pending_discovery"))
    if maintenance:
        selected = None
    else:
        try:
            selected = select(FrontierGraph.load(graph_path))["id"]
        except ValueError as error:
            if "no reachable uncovered" not in str(error):
                raise
            selected = None
    native = _native_pin(cycle)
    source_commit = _git_ok(repo, "rev-parse", "HEAD")
    key = {"cycle_root": str(root), "next_index": cycle["next_index"],
           "graph_sha256": cycle["graph_sha256"], "selected_edge": selected,
           "maintenance": maintenance,
           "tool_sha256": tool_sha256(repo), "native_sha256": native}
    job_id = "frontier-step-" + hashlib.sha256(canonical_bytes(key)).hexdigest()[:24]
    try:
        store.job(job_id)
    except JobStoreError:
        pass
    else:
        return None
    packet = {"kind": "jfg-autonomy-frontier-step", "schema": 1,
              "job_id": job_id, "source_commit": source_commit,
              "registration_sha256": file_sha256(state / REGISTRATION),
              "cycle_root": str(root), "cycle_state_sha256": file_sha256(root / "state.json"),
              "next_index": cycle["next_index"], "selected_edge": selected,
              "maintenance": maintenance,
              "emulator": data["emulator"], "rom": data["rom"],
              "rom_sha256": data["rom_sha256"], "script": data["script"],
              "script_sha256": data["script_sha256"],
              "native_sha256": native, "timeout_seconds": 1800}
    path = _packet_path(state, job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_bytes(packet)
    if path.exists() and path.read_bytes() != encoded:
        raise SupervisorError("frontier job ID names different packet")
    if not path.exists():
        _write_json_atomic(path, packet)
    digest = hashlib.sha256(encoded).hexdigest()
    store.enqueue(JobSpec(job_id, pins(repo, packet), (PREFIX + digest,), (),
                          "oracle:frontier", 1, "json_complete"))
    return job_id


def _job_result(repo: Path, cycle: dict, index: int, edge: str | None,
                *, maintenance: bool = False,
                start_sha256: str | None = None,
                cycle_path: Path | None = None) -> dict | None:
    if any(cycle.get(name) is not None for name in
           ("pending_node_verification", "pending_export",
            "pending_verification", "pending_discovery")):
        return None
    if maintenance and cycle["next_index"] == index and edge is None and \
            cycle_path is not None and start_sha256 is not None and \
            file_sha256(cycle_path) != start_sha256:
        return {"outcome": "maintained", "result": None, "result_sha256": None}
    if cycle["next_index"] == index and edge is None and \
            cycle.get("status") == "frontier_exhausted":
        return {"outcome": "frontier_exhausted", "result": None,
                "result_sha256": None}
    if cycle["next_index"] != index + 1 or len(cycle["jobs"]) <= index:
        return None
    entry = cycle["jobs"][index]
    if entry["index"] != index or entry["edge"] != edge:
        raise SupervisorError("frontier cycle advanced a different edge")
    path = resolve_pointer(entry["result"], _private(repo))
    result = json.loads(path.read_text())
    if result.get("kind") != "jfg-phase95-frontier-result" or \
            result.get("edge_id") != edge or result.get("outcome") != entry["outcome"] or \
            result.get("planner_source_stable") is not True:
        raise SupervisorError("frontier cycle result is not a stable bounded job")
    return {"outcome": entry["outcome"], "result": entry["result"],
            "result_sha256": file_sha256(path)}


def run_lease(store: JobStore, lease: dict, repo: Path, state: Path,
              *, command_runner=bounded_command) -> str:
    job_id, token, attempt = lease["job_id"], lease["token"], lease["attempt"]
    attempt_dir = state / "attempts" / job_id / f"{attempt:04d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    result_path = attempt_dir / "result.json"
    try:
        for previous in store.attempt_history(job_id):
            if previous["number"] >= attempt or previous["outcome"] != "expired":
                continue
            prior = state / "attempts" / job_id / f"{previous['number']:04d}"
            if not expired_attempt_contained(prior):
                raise SupervisorError("expired frontier worker is not proved contained")
        packet_file = _packet_path(state, job_id)
        packet = json.loads(packet_file.read_text())
        digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if packet.get("kind") != "jfg-autonomy-frontier-step" or \
                packet.get("schema") != 1 or packet.get("job_id") != job_id or \
                type(packet.get("maintenance")) is not bool or \
                (packet["maintenance"] and packet.get("selected_edge") is not None) or \
                lease["spec"]["inputs"] != [PREFIX + digest] or \
                file_sha256(state / REGISTRATION) != packet["registration_sha256"] or \
                pins(repo, packet) != lease["spec"]["pins"] or \
                packet["rom_sha256"] != lease["spec"]["pins"]["rom_sha256"] or \
                file_sha256(Path(packet["script"])) != packet["script_sha256"]:
            raise SupervisorError("frontier packet or pinned inputs changed")
        root, cycle = _cycle(repo, registration(repo, state))
        if str(root) != packet["cycle_root"] or \
                _native_pin(cycle) != packet["native_sha256"]:
            raise SupervisorError("frontier cycle registration or native pin changed")
        index = packet["next_index"]
        if cycle["next_index"] == index and \
                file_sha256(root / "state.json") != packet["cycle_state_sha256"] and \
                cycle["attempt"] == 0 and not packet["maintenance"]:
            raise SupervisorError("frontier state changed before worker lease")
        store.start(job_id, token)
        observed = _job_result(
            repo, cycle, index, packet["selected_edge"],
            maintenance=packet["maintenance"],
            start_sha256=packet["cycle_state_sha256"],
            cycle_path=root / "state.json")
        if observed is None:
            if cycle["next_index"] not in (index, index + 1):
                raise SupervisorError("frontier cycle advanced beyond pinned step")
            budget = ("0" if packet["maintenance"] or cycle["next_index"] != index
                      else "1")
            job_output = (root / f"job-{index:04d}-{cycle['attempt'] + 1:02d}"
                          if budget == "1" else None)
            argv = [real_python_executable(), "-m", "scripts.phase95_frontier_cycle",
                    "--output", str(root), "--resume", "--max-jobs", budget,
                    "--emulator", packet["emulator"], "--rom", packet["rom"],
                    "--script", packet["script"], "--rom-sha256", packet["rom_sha256"]]
            code, reason = command_runner(
                argv, repo, attempt_dir / "frontier.stdout",
                attempt_dir / "frontier.stderr",
                time.monotonic() + packet["timeout_seconds"],
                lambda: store.heartbeat(job_id, token, ttl=120), state / "PAUSED",
                guard_record=attempt_dir / "frontier.guard.json",
                memory_limit_bytes=12 * 1024 * 1024 * 1024,
                cpu_seconds=3600,
                minimum_free_bytes=MIN_FREE_BYTES,
                output_tree=job_output,
                max_output_tree_bytes=(MAX_STEP_BYTES if job_output is not None
                                       else None))
            if code != 0 or reason is not None:
                raise SupervisorError(f"frontier worker stopped: {reason or code}")
            _, cycle = _cycle(repo, registration(repo, state))
            observed = _job_result(
                repo, cycle, index, packet["selected_edge"],
                maintenance=packet["maintenance"],
                start_sha256=packet["cycle_state_sha256"],
                cycle_path=root / "state.json")
        if observed is None:
            raise SupervisorError("frontier worker did not seal its declared step")
        if pins(repo, packet) != lease["spec"]["pins"]:
            raise SupervisorError("frontier tools changed during worker run")
        _write_json_atomic(result_path, {
            "schema": 1, "complete": True, "kind": "frontier-cycle-execution",
            "job_id": job_id, "attempt": attempt, "packet_sha256": digest,
            "pins": lease["spec"]["pins"], "cycle_index": index,
            "edge_id": packet["selected_edge"], **observed,
            "cycle_state_sha256": file_sha256(root / "state.json"),
            "native_parity_verified": False})
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, result_path)
        store.pass_job(job_id, token)
        return f"{job_id}: frontier {observed['outcome']} sealed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        _write_json_atomic(result_path, {
            "schema": 1, "complete": False, "kind": "frontier-cycle-execution",
            "job_id": job_id, "attempt": attempt,
            "stop_reason": str(error)[:300]})
        try:
            store.fail_job(job_id, token, str(error)[:300],
                           blocked=isinstance(error, SupervisorError))
        except JobStoreError:
            pass
        return f"{job_id}: frontier worker stopped ({error})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--cycle", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(register(args.repo, args.state, args.cycle,
                              args.emulator, args.rom, args.script,
                              args.rom_sha256), sort_keys=True))


if __name__ == "__main__":
    main()
