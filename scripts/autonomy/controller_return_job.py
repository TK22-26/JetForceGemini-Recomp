"""Ledger-backed, model-free paired controller-return capture."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from scripts.autonomy.job_store import ID_RE, SHA256_RE, JobSpec, JobStore, JobStoreError
from scripts.autonomy.process_guard import real_python_executable
from scripts.autonomy.supervisor import (
    PIN_FILES, SupervisorError, _git_ok, _inside, _write_json_atomic,
    bounded_command, canonical_bytes, expired_attempt_contained, file_sha256,
)
from scripts import phase9_controller_return_pair as pair
from scripts.phase9_controller_return import compare
from scripts.phase9_event_trace import validate_windows
from scripts.phase95_bridge import runtime_digest


TOOL_FILES = (
    "scripts/autonomy/atomic_file.py",
    "scripts/autonomy/controller_return_job.py",
    "scripts/autonomy/supervisor.py", "scripts/autonomy/job_store.py",
    "scripts/autonomy/process_guard.py",
    "scripts/phase9_controller_return_pair.py",
    "scripts/phase9_controller_return.py", "scripts/phase9_event_trace.py",
    "scripts/phase9_controller_callers.py",
    "scripts/phase9_poll_semantic_pair.py",
    "scripts/phase95_native_replay.py", "scripts/phase95_oracle_replay.py",
    "scripts/phase9_oracle_instruction_effects.py",
    "scripts/phase9_point_probe.py",
    "scripts/phase9_bizhawk_oracle.lua", "scripts/phase95_bridge.py",
    "src/boot/native_boot.cpp",
)
SOURCE_NAMES = ("export-manifest.json", "controller.input", "initial.flash",
                "initial.pak")


def tool_sha256(repo: Path) -> str:
    value = hashlib.sha256()
    for relative in TOOL_FILES:
        value.update(relative.encode("ascii"))
        value.update(bytes.fromhex(file_sha256(repo / relative)))
    return value.hexdigest()


def job_id_for(input_sha: str, native_sha: str, emulator_sha: str,
               target: int, windows: tuple[tuple[int, int], ...],
               return_pc: int, tool_sha: str,
               caller_event_id: str | None = None,
               caller_report_sha256: str | None = None) -> str:
    identity = {
        "input_sha256": input_sha, "native_sha256": native_sha,
        "emulator_sha256": emulator_sha, "target": target,
        "windows": windows, "return_pc": return_pc,
        "tool_sha256": tool_sha,
    }
    if caller_event_id is not None:
        identity["caller_event_id"] = caller_event_id
        identity["caller_report_sha256"] = caller_report_sha256
    value = hashlib.sha256(canonical_bytes(identity)).hexdigest()[:24]
    return "controller-return-" + value


def _caller_context(store: JobStore, repo: Path, state: Path,
                    packet: dict) -> dict | None:
    event_id = packet.get("caller_event_id")
    if event_id is None:
        return None
    from scripts.autonomy.event_pair_job import sealed_context as sealed_event
    context = sealed_event(store, repo, state, event_id)
    event = context["packet"]
    report = context["caller_report"]
    if report is None:
        raise SupervisorError("controller caller event has no caller report")
    callers = {item["unique_caller"] for item in report["windows"]
               if item["rows"] > 0}
    if (len(callers) != 1 or None in callers or
            packet["return_pc"] not in callers or
            packet["caller_report_sha256"] !=
                file_sha256(context["caller_report_path"]) or
            packet["source_export"] != event["source_export"] or
            packet["target"] != event["target"] or
            packet["event_windows"] != event["event_windows"] or
            any(packet["pin_files"][key] != event["pin_files"][key]
                for key in ("rom", "emulator"))):
        raise SupervisorError("controller caller event does not pin this probe")
    return context


def pins(packet: dict, repo: Path) -> dict[str, str]:
    return {"source_commit": packet["source_commit"],
            "tool_sha256": tool_sha256(repo),
            **{key + "_sha256": file_sha256(
                Path(packet["pin_files"][key])) for key in PIN_FILES}}


def validate(packet: dict, repo: Path, state: Path) -> None:
    required = {"schema", "job_id", "source_commit", "pin_files",
                "source_export", "target", "event_windows", "return_pc",
                "timeout_seconds", "native_runtime_sha256",
                "emulator_runtime_sha256", "evidence_files"}
    optional = {"caller_event_id", "caller_report_sha256"}
    if (not isinstance(packet, dict) or not required <= set(packet) or
            not set(packet) <= required | optional or
            ("caller_event_id" in packet) !=
                ("caller_report_sha256" in packet) or
            packet["schema"] != 1 or
            not isinstance(packet["job_id"], str) or
            not ID_RE.fullmatch(packet["job_id"]) or
            not isinstance(packet["source_commit"], str) or
            _git_ok(repo, "rev-parse", "--verify",
                    packet["source_commit"] + "^{commit}") !=
            packet["source_commit"] or
            not isinstance(packet["pin_files"], dict) or
            set(packet["pin_files"]) != set(PIN_FILES) or
            type(packet["target"]) is not int or
            not 120 <= packet["target"] <= 100_000 or
            type(packet["timeout_seconds"]) is not int or
            not 60 <= packet["timeout_seconds"] <= 1800 or
            not isinstance(packet["return_pc"], str) or
            len(packet["return_pc"]) != 10 or
            not packet["return_pc"].startswith("0x") or
            any(char not in "0123456789abcdef"
                for char in packet["return_pc"][2:])):
        raise SupervisorError("invalid controller-return packet")
    if "caller_event_id" in packet and (
            not isinstance(packet["caller_event_id"], str) or
            not ID_RE.fullmatch(packet["caller_event_id"]) or
            not isinstance(packet["caller_report_sha256"], str) or
            not SHA256_RE.fullmatch(packet["caller_report_sha256"])):
        raise SupervisorError("invalid controller caller evidence pin")
    windows = validate_windows(packet["event_windows"], poll_hashes=True,
                               update_hashes=True, vi_trace=True)
    if (not windows or windows[-1][1] >= packet["target"] or
            not 0x80000000 <= int(packet["return_pc"], 16) <= 0x803FFFFC or
            int(packet["return_pc"], 16) % 4):
        raise SupervisorError("invalid controller-return window or PC")
    source = Path(packet["source_export"])
    if (not source.is_absolute() or not source.is_dir() or
            not _inside(source, repo / "tools" / "private")):
        raise SupervisorError("controller-return source is not private")
    for key in PIN_FILES:
        value = packet["pin_files"][key]
        if (not isinstance(value, str) or not Path(value).is_absolute() or
                not Path(value).is_file()):
            raise SupervisorError("controller-return input pin is missing")
    for key in ("native_runtime_sha256", "emulator_runtime_sha256"):
        if (not isinstance(packet[key], str) or
                not SHA256_RE.fullmatch(packet[key])):
            raise SupervisorError("controller-return runtime pin is invalid")
    if (runtime_digest(Path(packet["pin_files"]["native"]).parent) !=
            packet["native_runtime_sha256"] or
            runtime_digest(Path(packet["pin_files"]["emulator"]).parent) !=
            packet["emulator_runtime_sha256"] or
            not pair.native_capable(Path(packet["pin_files"]["native"]))):
        raise SupervisorError("controller-return runtime changed or lacks hook")
    evidence = packet["evidence_files"]
    if (not isinstance(evidence, list) or len(evidence) != len(SOURCE_NAMES) or
            [item.get("path") for item in evidence if isinstance(item, dict)] !=
            [str(source / name) for name in SOURCE_NAMES]):
        raise SupervisorError("controller-return source evidence is incomplete")
    for item in evidence:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"} or
                not isinstance(item["sha256"], str) or
                not SHA256_RE.fullmatch(item["sha256"]) or
                file_sha256(Path(item["path"])) != item["sha256"]):
            raise SupervisorError("controller-return source evidence changed")


def queue(store: JobStore, repo: Path, state: Path, source: Path,
          executable: Path, emulator: Path, rom: Path, rom_sha256: str,
          *, target: int, windows: tuple[tuple[int, int], ...],
          return_pc: int, timeout: int = 600,
          caller_event_id: str | None = None) -> str:
    source, executable, emulator, rom = (
        Path(value).resolve(strict=True) for value in
        (source, executable, emulator, rom))
    windows = validate_windows(windows, poll_hashes=True,
                               update_hashes=True, vi_trace=True)
    if (not windows or type(return_pc) is not int or
            not 0x80000000 <= return_pc <= 0x803FFFFC or return_pc % 4):
        raise SupervisorError("invalid controller-return queue request")
    plan = pair._plan(source, executable, emulator, rom,
                      rom_sha256, target, timeout)
    packet = {
        "schema": 1,
        "source_commit": _git_ok(repo, "rev-parse", "HEAD"),
        "pin_files": {"rom": str(rom), "emulator": str(emulator),
                      "native": str(executable)},
        "source_export": str(source), "target": target,
        "event_windows": [list(window) for window in windows],
        "return_pc": f"0x{return_pc:08x}",
        "timeout_seconds": timeout,
        "native_runtime_sha256": runtime_digest(executable.parent),
        "emulator_runtime_sha256": runtime_digest(emulator.parent),
        "evidence_files": [
            {"path": str(source / name), "sha256": file_sha256(source / name)}
            for name in SOURCE_NAMES],
    }
    if caller_event_id is not None:
        from scripts.autonomy.event_pair_job import sealed_context as sealed_event
        context = sealed_event(store, repo, state, caller_event_id)
        if context["caller_report_path"] is None:
            raise SupervisorError("caller event has no bounded caller report")
        packet["caller_event_id"] = caller_event_id
        packet["caller_report_sha256"] = file_sha256(
            context["caller_report_path"])
        _caller_context(store, repo, state, packet)
    job_id = job_id_for(plan["input_sha256"], plan["native_executable_sha256"],
                        plan["emulator_sha256"], target, windows,
                        return_pc, tool_sha256(repo), caller_event_id,
                        packet.get("caller_report_sha256"))
    packet["job_id"] = job_id
    validate(packet, repo, state)
    encoded = canonical_bytes(packet)
    directory = state / "controller-return-packets"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (job_id + ".json")
    if path.exists() and path.read_bytes() != encoded:
        raise SupervisorError("controller-return job ID names another packet")
    if not path.exists():
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
    store.enqueue(JobSpec(job_id, pins(packet, repo),
                          ("controller-return-packet:" +
                           hashlib.sha256(encoded).hexdigest(),),
                          (caller_event_id,) if caller_event_id else (),
                          "emulator:bizhawk", 1, "json_complete"))
    return job_id


def _complete(attempt_dir: Path, packet: dict) -> dict | None:
    output = attempt_dir / "pair"
    if not all((output / relative).is_file() for relative in (
            "plan.json", "pair-result.json", "controller-return-report.json",
            "native/native-result.json", "oracle/oracle-result.json")):
        return None
    pins_in = packet["pin_files"]
    result = pair.run(
        output, Path(packet["source_export"]), Path(pins_in["native"]),
        Path(pins_in["emulator"]), Path(pins_in["rom"]),
        file_sha256(Path(pins_in["rom"])), target=packet["target"],
        windows=tuple(tuple(window) for window in packet["event_windows"]),
        return_pc=int(packet["return_pc"], 16),
        timeout=packet["timeout_seconds"])
    if (result.get("complete") is not True or
            result.get("alignment_validated") is not False or
            result.get("parity_verified") is not False or
            result.get("controller_return_report_sha256") !=
            file_sha256(output / "controller-return-report.json")):
        raise SupervisorError("controller-return pair is incomplete")
    return {"pair_result_sha256": file_sha256(output / "pair-result.json"),
            "controller_return_report_sha256":
                file_sha256(output / "controller-return-report.json"),
            "shared_polls": result["shared_polls"],
            "matching_shared_poll_prefix":
                result["matching_shared_poll_prefix"],
            "first_same_poll_difference": result["first_same_poll_difference"]}


def sealed_context(store: JobStore, repo: Path, state: Path,
                   job_id: str) -> dict:
    """Verify a passed pair without rerunning or changing its capture."""
    job = store.job(job_id)
    if (job["state"] != "passed" or not job["sealed_artifact"] or
            not job["sealed_sha256"]):
        raise SupervisorError("controller-return pair is not sealed")
    packet = json.loads((state / "controller-return-packets" /
                         (job_id + ".json")).read_text(encoding="utf-8"))
    validate(packet, repo, state)
    _caller_context(store, repo, state, packet)
    packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    sealed = Path(job["sealed_artifact"]).resolve(strict=True)
    attempt_root = (state / "attempts" / job_id).resolve()
    if (not sealed.is_relative_to(attempt_root) or sealed.name != "result.json" or
            file_sha256(sealed) != job["sealed_sha256"] or
            job["spec"]["inputs"] !=
            ["controller-return-packet:" + packet_sha] or
            job["spec"]["prerequisites"] !=
                ([packet["caller_event_id"]] if "caller_event_id" in packet
                 else [])):
        raise SupervisorError("sealed controller-return identity changed")
    result = json.loads(sealed.read_text(encoding="utf-8"))
    pair_root = Path(result.get("pair_root", "")).resolve(strict=True)
    if (pair_root.name != "pair" or
            not pair_root.is_relative_to(attempt_root) or
            result.get("kind") != "controller-return-execution" or
            result.get("complete") is not True or
            result.get("job_id") != job_id or
            result.get("packet_sha256") != packet_sha or
            result.get("pins") != job["spec"]["pins"] or
            result.get("alignment_validated") is not False or
            result.get("parity_verified") is not False):
        raise SupervisorError("sealed controller-return result changed")
    plan_path = pair_root / "plan.json"
    pair_result_path = pair_root / "pair-result.json"
    report_path = pair_root / "controller-return-report.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    pair_result = json.loads(pair_result_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    windows = tuple(tuple(window) for window in packet["event_windows"])
    recomputed = compare(
        pair_root / "native" / "retrace-hashes.jsonl.controller-return.tsv",
        pair_root / "oracle" / "controller-return.tsv", windows)
    if (plan.get("kind") != pair.KIND or
            plan.get("source_export") != packet["source_export"] or
            plan.get("native_executable") != packet["pin_files"]["native"] or
            plan.get("emulator") != packet["pin_files"]["emulator"] or
            plan.get("rom") != packet["pin_files"]["rom"] or
            plan.get("target") != packet["target"] or
            plan.get("event_windows") != packet["event_windows"] or
            plan.get("return_pc") != packet["return_pc"] or
            plan.get("native_runtime_sha256") !=
            packet["native_runtime_sha256"] or
            plan.get("emulator_runtime_sha256") !=
            packet["emulator_runtime_sha256"] or
            pair_result.get("kind") != pair.KIND or
            pair_result.get("complete") is not True or
            pair_result.get("plan_sha256") != file_sha256(plan_path) or
            pair_result.get("native_result_sha256") != file_sha256(
                pair_root / "native" / "native-result.json") or
            pair_result.get("oracle_result_sha256") != file_sha256(
                pair_root / "oracle" / "oracle-result.json") or
            pair_result.get("controller_return_report_sha256") !=
            file_sha256(report_path) or
            pair_result.get("alignment_validated") is not False or
            pair_result.get("parity_verified") is not False or
            result.get("pair_result_sha256") != file_sha256(pair_result_path) or
            result.get("controller_return_report_sha256") !=
            file_sha256(report_path) or
            report != recomputed or
            report.get("alignment_validated") is not False or
            report.get("parity_verified") is not False or
            any(result.get(key) != pair_result.get(key) for key in (
                "shared_polls", "matching_shared_poll_prefix",
                "first_same_poll_difference"))):
        raise SupervisorError("sealed controller-return report is inconsistent")
    return {"job": job, "packet": packet, "sealed": sealed,
            "pair_root": pair_root, "report_path": report_path,
            "report": report}


def run_lease(store: JobStore, lease: dict, repo: Path, state: Path) -> str:
    job_id, token, attempt = lease["job_id"], lease["token"], lease["attempt"]
    attempt_dir = state / "attempts" / job_id / f"{attempt:04d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    result_path = attempt_dir / "result.json"
    try:
        packet = json.loads((state / "controller-return-packets" /
                             (job_id + ".json")).read_text(encoding="utf-8"))
        validate(packet, repo, state)
        _caller_context(store, repo, state, packet)
        packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        if (lease["spec"]["inputs"] !=
                ["controller-return-packet:" + packet_sha] or
                lease["spec"]["prerequisites"] !=
                    ([packet["caller_event_id"]] if "caller_event_id" in packet
                     else []) or
                pins(packet, repo) != lease["spec"]["pins"]):
            raise SupervisorError("controller-return packet or pins changed")
        for previous in store.attempt_history(job_id):
            if previous["number"] >= attempt or previous["outcome"] != "expired":
                continue
            prior = state / "attempts" / job_id / f"{previous['number']:04d}"
            if not expired_attempt_contained(prior):
                raise SupervisorError("expired controller-return worker may be live")
            recovered = _complete(prior, packet)
            if recovered is not None:
                _write_json_atomic(result_path, {
                    "schema": 1, "complete": True,
                    "kind": "controller-return-execution", "job_id": job_id,
                    "attempt": attempt,
                    "recovered_from_attempt": previous["number"],
                    "pair_root": str(prior / "pair"),
                    "packet_sha256": packet_sha,
                    "pins": lease["spec"]["pins"],
                    "alignment_validated": False,
                    "parity_verified": False, **recovered})
                store.start(job_id, token)
                store.verify(job_id, token)
                store.seal_artifact(job_id, token, result_path)
                store.pass_job(job_id, token)
                return f"{job_id}: prior controller-return pair recovered"
        store.start(job_id, token)
        pins_in = packet["pin_files"]
        command = [real_python_executable(), "-m",
                   "scripts.phase9_controller_return_pair",
                   str(attempt_dir / "pair"), "--source", packet["source_export"],
                   "--executable", pins_in["native"],
                   "--emulator", pins_in["emulator"], "--rom", pins_in["rom"],
                   "--rom-sha256", lease["spec"]["pins"]["rom_sha256"],
                   "--target", str(packet["target"]),
                   "--return-pc", packet["return_pc"],
                   "--timeout", str(packet["timeout_seconds"])]
        for first, last in packet["event_windows"]:
            command.extend(("--window", f"{first}:{last}"))
        code, reason = bounded_command(
            command, repo, attempt_dir / "pair.stdout",
            attempt_dir / "pair.stderr",
            time.monotonic() + 2 * packet["timeout_seconds"] + 60,
            lambda: store.heartbeat(job_id, token, ttl=120),
            state / "PAUSED", guard_record=attempt_dir / "pair.guard.json",
            cpu_seconds=2 * packet["timeout_seconds"] + 60)
        if code != 0 or reason is not None:
            raise RuntimeError(f"bounded controller-return worker failed: {reason or code}")
        complete = _complete(attempt_dir, packet)
        if complete is None:
            raise SupervisorError("controller-return worker produced no pair")
        validate(packet, repo, state)
        _caller_context(store, repo, state, packet)
        if pins(packet, repo) != lease["spec"]["pins"]:
            raise SupervisorError("controller-return pins changed during capture")
        _write_json_atomic(result_path, {
            "schema": 1, "complete": True,
            "kind": "controller-return-execution", "job_id": job_id,
            "attempt": attempt, "pair_root": str(attempt_dir / "pair"),
            "packet_sha256": packet_sha, "pins": lease["spec"]["pins"],
            "alignment_validated": False, "parity_verified": False,
            **complete})
        store.verify(job_id, token)
        store.seal_artifact(job_id, token, result_path)
        store.pass_job(job_id, token)
        return f"{job_id}: controller-return pair sealed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        _write_json_atomic(result_path, {
            "schema": 1, "complete": False,
            "kind": "controller-return-execution", "job_id": job_id,
            "attempt": attempt, "stop_reason": str(error)[:300]})
        try:
            store.fail_job(job_id, token, str(error)[:300],
                           blocked=isinstance(error, SupervisorError))
        except JobStoreError:
            pass
        return f"{job_id}: controller-return pair blocked ({error})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path,
                        default=Path(__file__).resolve().parents[2] /
                        "tools" / "private" / "autonomy")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--target", type=int, default=1500)
    parser.add_argument("--window", action="append", required=True)
    parser.add_argument("--return-pc", type=lambda value: int(value, 0),
                        required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    try:
        windows = tuple(tuple(map(int, value.split(":")))
                        for value in args.window)
    except ValueError as error:
        parser.error(f"invalid --window: {error}")
    repo = Path(__file__).resolve().parents[2]
    state = args.state.resolve()
    if not state.is_relative_to((repo / "tools" / "private").resolve()):
        raise ValueError("controller-return state must be private")
    with JobStore(state / "jobs.sqlite") as store:
        print(queue(store, repo, state, args.source, args.executable,
                    args.emulator, args.rom, args.rom_sha256,
                    target=args.target, windows=windows,
                    return_pc=args.return_pc, timeout=args.timeout))


if __name__ == "__main__":
    main()
