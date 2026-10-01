"""Opt-in real native build/replay smoke with an explicitly synthetic candidate.

The implementation and approval are fixtures. This proves the local build and
replay plumbing against an existing sealed baseline, not independent review,
gameplay improvement, alignment, or parity. No model or API call is made.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.autonomy.job_store import JobSpec, JobStore
from scripts.autonomy.scheduler import advance_jobs
from scripts.autonomy.supervisor import (
    ROOT, SupervisorError, _inside, enqueue_packet, file_sha256, run_once,
    validate_packet,
)


DEFAULT_BASELINE = "updates-rebase-da5cdf775ea4fd64a52c11a1"
MARKER = "docs/planning/autonomy-native-retest-smoke.txt"


def _baseline(source_state: Path, state: Path, baseline_id: str) -> dict:
    """Copy only sealed baseline evidence into a separate smoke ledger."""
    with JobStore(source_state / "jobs.sqlite") as original:
        job = original.job(baseline_id)
    if job["state"] != "passed" or not job["sealed_artifact"]:
        raise SupervisorError("baseline update job is not sealed and passed")
    original_result = Path(job["sealed_artifact"]).resolve(strict=True)
    if (not original_result.is_relative_to(
            (source_state / "attempts" / baseline_id).resolve()) or
            file_sha256(original_result) != job["sealed_sha256"]):
        raise SupervisorError("baseline update seal changed")
    packet_source = source_state / "update-packets" / (baseline_id + ".json")
    packet = json.loads(packet_source.read_text(encoding="utf-8"))
    result = json.loads(original_result.read_text(encoding="utf-8"))
    if (packet.get("job_id") != baseline_id or
            result.get("job_id") != baseline_id or
            result.get("complete") is not True):
        raise SupervisorError("baseline packet/result mismatch")
    packet_dest = state / "update-packets" / packet_source.name
    packet_dest.parent.mkdir(parents=True)
    shutil.copy2(packet_source, packet_dest)
    original_attempt = original_result.parent
    target_attempt = state / "attempts" / baseline_id / "0001"
    files = (
        "result.json", "update-comparison.json",
        "native/native-result.json", "native/retrace-hashes.jsonl",
        "native/retrace-hashes.jsonl.updates.jsonl",
        "oracle/oracle-result.json", "oracle/update-hashes.jsonl",
        "oracle/checkpoints.tsv",
    )
    for relative in files:
        source = original_attempt / relative
        target = target_attempt / relative
        if not source.is_file():
            raise SupervisorError("sealed baseline lacks smoke evidence: " + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if file_sha256(source) != file_sha256(target):
            raise SupervisorError("baseline smoke copy changed: " + relative)
    if file_sha256(target_attempt / "result.json") != job["sealed_sha256"]:
        raise SupervisorError("copied baseline seal changed")
    spec = job["spec"]
    with JobStore(state / "jobs.sqlite") as store:
        store.enqueue(JobSpec(baseline_id, spec["pins"], tuple(spec["inputs"]),
                              (), "smoke:baseline", 0, "json_complete"))
        lease = store.lease_job(baseline_id, "smoke-import")
        if lease is None:
            raise SupervisorError("could not lease imported baseline")
        store.start(baseline_id, lease["token"])
        store.verify(baseline_id, lease["token"])
        store.seal_artifact(baseline_id, lease["token"],
                            target_attempt / "result.json")
        store.pass_job(baseline_id, lease["token"])
    return packet


def _recipe(baseline_id: str, cmake: Path) -> dict:
    generated = (ROOT / "tools" / "results" / "phase4" /
                 "semantic-audit-current-v3" / "normalized-phase8-hash-v1")
    audio = ROOT / "tools" / "results" / "phase4" / "private-audio-g2"
    runtime = ROOT / "tools" / "upstream" / "N64ModernRuntime" / "librecomp" / "include"
    rt64 = ROOT / "tools" / "upstream" / "rt64"
    libultra = ROOT / "captures" / "private" / "phase6" / "libultra-identification.json"
    inputs = (generated / "runtime-manifest.canonical.sha256",
              audio / "production-audio-adapter.cpp", rt64 / "CMakeLists.txt",
              libultra)
    for path in inputs:
        if not path.is_file():
            raise SupervisorError("candidate build fixture input missing: " + str(path))
    if not runtime.is_dir() or not cmake.is_file():
        raise SupervisorError("candidate build CMake or runtime include root missing")
    def cmake_path(path: Path) -> str:
        return str(path.resolve()).replace("\\", "/")
    configure = [str(cmake), "-S", "{source}", "-B", "{build}",
                 "-G", "Visual Studio 17 2022", "-A", "x64",
                 "-DJFG_ENABLE_GENERATED_CODE=ON",
                 "-DJFG_BUILD_PHASE6_NATIVE_BOOT=ON",
                 "-DJFG_BUILD_PHASE7_RT64_RUNNER=ON",
                 "-DJFG_BUILD_PHASE8_LIVE=ON",
                 "-DJFG_ENABLE_RT64=ON",
                 "-DJFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF",
                 "-DJFG_BUILD_TESTS=OFF",
                 "-DJFG_GENERATED_ROOT=" + cmake_path(generated),
                 "-DJFG_PHASE6_LIBULTRA_IDENTIFICATION=" + cmake_path(libultra),
                 "-DJFG_PHASE8_PRIVATE_AUDIO_ADAPTER_ROOT=" + cmake_path(audio),
                 "-DJFG_PHASE8_PRIVATE_AUDIO_RUNTIME_INCLUDE=" + cmake_path(runtime),
                 "-DJFG_RT64_ROOT=" + cmake_path(rt64)]
    return {
        "baseline_update_id": baseline_id,
        "configure_argv": configure,
        "build_argv": [str(cmake), "--build", "{build}", "--config", "Release",
                       "--target", "jfg-native-boot", "--parallel", "8"],
        "executable": "Release/jfg-native-boot.exe",
        "build_inputs": [{"path": str(path.resolve()), "sha256": file_sha256(path)}
                         for path in inputs],
        "timeout_seconds": 3600,
    }


def smoke(state: Path, source_state: Path, baseline_id: str,
          cmake: Path) -> dict:
    state, source_state = state.resolve(), source_state.resolve(strict=True)
    if (not _inside(state, ROOT / "tools" / "private") or state.exists() or
            not _inside(source_state, ROOT / "tools" / "private") or
            state == source_state):
        raise SupervisorError("smoke state must be new, private, and separate")
    if len(str(state)) > 120:
        raise SupervisorError("smoke state path is too long for Windows Git")
    state.mkdir(parents=True)
    baseline = _baseline(source_state, state, baseline_id)
    fake_agent = state / "fixture_implementer.py"
    fake_agent.write_text(
        "from pathlib import Path\nimport sys\nsys.stdin.read()\n"
        f"Path({MARKER!r}).write_text('synthetic native retest\\n', encoding='utf-8')\n",
        encoding="utf-8")
    packet = {
        "schema": 1, "job_id": "sn", "kind": "implement",
        "source_commit": baseline["source_commit"],
        "pin_files": baseline["pin_files"],
        "prompt": "Add a synthetic smoke marker; do not change gameplay code.",
        "timeout_seconds": 240,
        "validation": [[sys.executable, "-c",
                        "from pathlib import Path; assert Path(" + repr(MARKER) +
                        ").read_text() == 'synthetic native retest\\n'"]],
        "prerequisites": [], "retry_budget": 0,
        "allowed_paths": [MARKER], "max_changed_files": 1,
        "evidence_files": [], "candidate_build": _recipe(baseline_id, cmake),
    }
    validate_packet(packet, ROOT)
    with JobStore(state / "jobs.sqlite") as store:
        enqueue_packet(store, state, packet, fake_agent)
    outcome = run_once(ROOT, state, fake_agent,
                       agent_prefix=[sys.executable, str(fake_agent)],
                       require_auth=False)
    if outcome != packet["job_id"] + ": candidate sealed":
        raise SupervisorError("synthetic implementation failed: " + outcome)
    fake_reviewer = state / "fixture_reviewer.py"
    fake_reviewer.write_text(
        "import json, pathlib, sys\n"
        "sys.stdin.read()\n"
        "pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1])"
        ".write_text(json.dumps({'verdict':'approve','findings':[],"
        "'confidence':'medium'}), encoding='utf-8')\n", encoding="utf-8")
    with JobStore(state / "jobs.sqlite") as store:
        review_jobs = advance_jobs(store, ROOT, state, fake_reviewer)
    review_id = packet["job_id"] + "-review"
    if review_jobs != [review_id]:
        raise SupervisorError("synthetic review was not queued")
    outcome = run_once(ROOT, state, fake_reviewer,
                       agent_prefix=[sys.executable, str(fake_reviewer)],
                       require_auth=False)
    if outcome != review_id + ": candidate sealed":
        raise SupervisorError("synthetic review failed: " + outcome)
    with JobStore(state / "jobs.sqlite") as store:
        retest_jobs = advance_jobs(store, ROOT, state, fake_reviewer)
    retest_id = review_id + "-native-retest"
    if retest_jobs != [retest_id]:
        raise SupervisorError("native retest was not queued")
    outcome = run_once(ROOT, state, fake_reviewer, allow_agent=False)
    with JobStore(state / "jobs.sqlite") as store:
        job = store.job(retest_id)
    if job["state"] != "passed" or not job["sealed_artifact"]:
        raise SupervisorError("real native retest did not seal: " + outcome)
    result = json.loads(Path(job["sealed_artifact"]).read_text(encoding="utf-8"))
    if (result.get("candidate_only") is not True or
            result.get("parity_verified") is not False or
            result.get("alignment_validated") is not False or
            result.get("build_closure_verified") is not False or
            result.get("input_prefix_match") is not True):
        raise SupervisorError("native smoke result violates diagnostic contract")
    return {"result": "passed", "candidate_only": True,
            "raw_frontier": result["raw_frontier"],
            "input_prefix_match": result["input_prefix_match"],
            "state": str(state)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--baseline-id", default=DEFAULT_BASELINE)
    parser.add_argument("--source-state", type=Path,
                        default=ROOT / "tools" / "private" / "autonomy")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--cmake", type=Path, default=Path(
        r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE"
        r"\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"))
    args = parser.parse_args()
    if not args.execute:
        parser.error("native retest smoke requires --execute")
    state = args.state or (ROOT / "tools" / "private" /
                           ("nrs-" + datetime.now(timezone.utc).strftime(
                               "%Y%m%dT%H%M%S%fZ")))
    try:
        print(json.dumps(smoke(state, args.source_state, args.baseline_id,
                               args.cmake.resolve(strict=True)), indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"native retest smoke failed: {error}; private state: {state}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
