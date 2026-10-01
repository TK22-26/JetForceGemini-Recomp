"""Opt-in, bounded end-to-end smoke of the ChatGPT Codex review worker.

Creates only synthetic data in ignored private storage. The implementation
producer is a local fixture; the independent reviewer is the real Codex CLI.
No ROM, emulator, native executable, API key, branch update, or push is used.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.autonomy.candidate_review import queue_review
from scripts.autonomy.job_store import JobStore
from scripts.autonomy.process_guard import owner_process_dead, real_python_executable
from scripts.autonomy.supervisor import (
    ROOT, SupervisorError, _git_ok, enqueue_packet, read_review, run_once,
    validate_packet,
)


def _git(repo: Path, *args: str) -> None:
    result = subprocess.run(["git", "-C", str(repo), *args], check=False,
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise SupervisorError(f"fixture git {args[0]} failed")


def _hard_kill_first_review(repo: Path, state: Path, codex_binary: Path,
                            review_job_id: str) -> None:
    if sys.platform != "win32":
        raise SupervisorError("hard-kill review smoke requires Windows Job Objects")
    runner = (
        "from pathlib import Path; import sys; "
        "from scripts.autonomy.supervisor import run_once; "
        "run_once(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))"
    )
    guard_path = state / "attempts" / review_job_id / "0001" / "agent.guard.json"
    with (state / "crashed-supervisor.stdout").open("wb") as output, \
            (state / "crashed-supervisor.stderr").open("wb") as errors:
        parent = subprocess.Popen(
            [real_python_executable(), "-c", runner, str(repo), str(state),
             str(codex_binary)], cwd=str(ROOT), stdout=output, stderr=errors)
        try:
            deadline = time.monotonic() + 90
            record = None
            while time.monotonic() < deadline:
                if parent.poll() is not None:
                    raise SupervisorError("first review supervisor exited before guard")
                if guard_path.is_file():
                    try:
                        record = json.loads(guard_path.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        record = None
                    if record and record.get("state") == "guarded":
                        break
                time.sleep(0.1)
            else:
                raise SupervisorError("first review child was not guarded within 90 seconds")
            child_pid = record.get("child_pid")
            parent.kill()
            parent.wait(timeout=10)
            if type(child_pid) is not int:
                raise SupervisorError("guard did not record a child PID")
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and not owner_process_dead(child_pid):
                time.sleep(0.1)
            if not owner_process_dead(child_pid):
                raise SupervisorError("Codex child survived its supervisor hard kill")
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=10)
    with JobStore(state / "jobs.sqlite") as store:
        lease_until = store.job(review_job_id)["lease_until"]
        if lease_until is None:
            raise SupervisorError("interrupted review lost its active lease")
        store.reclaim_expired(now=lease_until + 1)
        if store.job(review_job_id)["state"] != "queued":
            raise SupervisorError("expired review did not return to queue")


def smoke(state: Path, codex_binary: Path,
          *, hard_kill_review_once: bool = False) -> dict[str, object]:
    state = state.resolve()
    expected_root = (ROOT / "tools" / "private").resolve()
    if not state.is_relative_to(expected_root) or state.exists():
        raise SupervisorError("new smoke state must be under tools/private")
    state.mkdir(parents=True)
    repo = state / "fixture-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Autonomy Smoke")
    _git(repo, "config", "user.email", "autonomy-smoke@localhost")
    (repo / "README.md").write_text("A synthetic fixture.\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "Synthetic fixture")
    commit = _git_ok(repo, "rev-parse", "HEAD")
    pins = {}
    for key in ("rom", "emulator", "native"):
        path = state / (key + ".fixture")
        path.write_text("synthetic " + key + "\n", encoding="utf-8")
        pins[key] = str(path)
    fake_agent = state / "fixture_implementer.py"
    fake_agent.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "sys.stdin.read()\n"
        "Path('candidate.txt').write_text('fixed\\n', encoding='utf-8')\n",
        encoding="utf-8")
    packet = {
        "schema": 1, "job_id": "synthetic-implementation", "kind": "implement",
        "source_commit": commit, "pin_files": pins,
        "prompt": "Add candidate.txt containing fixed followed by a newline.",
        "timeout_seconds": 240,
        "validation": [[sys.executable, "-c",
                        "from pathlib import Path; assert Path('candidate.txt').read_text() == 'fixed\\n'"]],
        "prerequisites": [], "retry_budget": 0,
        "allowed_paths": ["candidate.txt"], "max_changed_files": 1,
        "evidence_files": [],
    }
    validate_packet(packet, repo)
    with JobStore(state / "jobs.sqlite") as store:
        enqueue_packet(store, state, packet, fake_agent)
    implementation = run_once(repo, state, fake_agent,
                              agent_prefix=[sys.executable, str(fake_agent)],
                              require_auth=False)
    if implementation != "synthetic-implementation: candidate sealed":
        raise SupervisorError("synthetic implementation did not seal: " + implementation)
    with JobStore(state / "jobs.sqlite") as store:
        review_job_id = queue_review(store, repo, state, codex_binary,
                                     "synthetic-implementation")
    if hard_kill_review_once:
        _hard_kill_first_review(repo, state, codex_binary, review_job_id)
    outcome = run_once(repo, state, codex_binary)
    if outcome != review_job_id + ": candidate sealed":
        raise SupervisorError("live review did not seal: " + outcome)
    with JobStore(state / "jobs.sqlite") as store:
        job = store.job(review_job_id)
        attempt_outcomes = [item["outcome"] for item in
                            store.attempt_history(review_job_id)]
    result_path = Path(job["sealed_artifact"])
    result = json.loads(result_path.read_text(encoding="utf-8"))
    review = read_review(result_path.parent / "last-message.txt")
    if (not result["complete"] or not result["candidate_only"] or
            result["changed_paths"] or
            len(result["candidate_retest_validation"]) != 1 or
            result["candidate_retest_validation"][0]["exit_code"] != 0 or
            (repo / "candidate.txt").exists()):
        raise SupervisorError("live review result violates candidate-only contract")
    expected_attempts = (["expired", "passed"] if hard_kill_review_once
                         else ["passed"])
    if attempt_outcomes != expected_attempts:
        raise SupervisorError("review attempts do not prove exact crash recovery")
    return {"result": "passed", "review_verdict": review["verdict"],
            "candidate_commit": result["candidate_commit"],
            "review_attempts": attempt_outcomes, "state": str(state)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="explicitly launch the ChatGPT-authenticated reviewer")
    parser.add_argument("--hard-kill-review-once", action="store_true",
                        help="kill first supervisor during a guarded Codex review, then retry")
    parser.add_argument("--codex-bin", type=Path,
                        default=Path(shutil.which("codex") or "codex"))
    parser.add_argument("--state", type=Path)
    args = parser.parse_args()
    if not args.execute:
        parser.error("live review smoke requires --execute")
    state = args.state or (ROOT / "tools" / "private" / "autonomy" /
                           ("live-review-smoke-" + datetime.now(timezone.utc).strftime(
                               "%Y%m%dT%H%M%SZ")))
    try:
        print(json.dumps(smoke(
            state, args.codex_bin.resolve(strict=True),
            hard_kill_review_once=args.hard_kill_review_once), indent=2))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"live review smoke failed: {error}; private state: {state}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
