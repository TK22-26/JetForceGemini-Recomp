"""Private event-logged entry point for an opt-in local supervisor task.

The scheduled task is not installed by importing or running this module.
Installation is a separate explicit action in install_windows_task.ps1.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from scripts.autonomy.continuous import serve
from scripts.autonomy.supervisor import ROOT, SupervisorError, _inside


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--codex-bin", type=Path, required=True)
    parser.add_argument("--max-agent-attempts-per-day", type=int, default=0)
    parser.add_argument("--poll-seconds", type=float, default=15)
    parser.add_argument("--audit-seconds", type=float, default=86_400)
    parser.add_argument("--max-cycles", type=int,
                        help="bounded smoke only; omit for the service")
    args = parser.parse_args(argv)
    repo = args.repo.resolve(strict=True)
    state = (args.state or repo / "tools" / "private" / "autonomy").resolve()
    if not _inside(state, repo / "tools" / "private"):
        parser.error("state must be beneath repo/tools/private")
    agent = args.codex_bin.resolve(strict=True)
    state.mkdir(parents=True, exist_ok=True)
    log = state / "supervisor-events.jsonl"

    def emit(event: dict) -> None:
        payload = {"utc": datetime.now(timezone.utc).isoformat(),
                   "pid": os.getpid(), **event}
        with log.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(payload, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    emit({"kind": "service-start", "agent_cap": args.max_agent_attempts_per_day,
          "bounded": args.max_cycles is not None})
    last_outcome = None
    last_logged = 0.0

    def on_cycle(event: dict) -> None:
        nonlocal last_outcome, last_logged
        now = time.monotonic()
        outcome = event.get("outcome")
        if (event.get("cycle") == 1 or outcome != last_outcome or
                now - last_logged >= 900):
            emit({"kind": "service-cycle", **event})
            last_logged = now
        last_outcome = outcome

    try:
        outcomes = serve(repo, state, agent, poll_seconds=args.poll_seconds,
              audit_seconds=args.audit_seconds,
              max_cycles=args.max_cycles,
              max_agent_attempts_per_utc_day=args.max_agent_attempts_per_day,
              on_cycle=on_cycle)
    except (SupervisorError, OSError, ValueError) as error:
        emit({"kind": "service-failed", "error": str(error)[:1024]})
        return 2
    emit({"kind": "service-stopped", "reason": "progress-stopped"
          if outcomes and outcomes[-1].startswith("progress-stopped:") else "cycle-limit"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
