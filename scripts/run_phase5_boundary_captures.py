"""Phase 5 boundary-function capture orchestrator.

Drives the private ``jfg_phase5_capture_producer`` over risk-weighted
boundary candidates until the acceptance target is met:

* capture succeeds and the in-process double replay is bit-identical;
* a second, separate process replays the written blob bit-identically
  (cross-process exact repeat); and
* a seeded one-byte fault is localized by the first-divergence tool.

Candidates are risk-weighted per the scope assessment: the earliest
functions of the main section (boot-boundary code) plus the first functions
of each overlay section (overlay entry boundaries), interleaved
deterministically.  Functions that crash, hang, or trap are recorded as
``unsafe-excluded`` and skipped — running an arbitrary generated body on a
zeroed world is not required to be safe, only attempted deterministically.

Outputs:
* private ledger JSON + capture blobs under ``captures/private/phase5/``
  (ignored, never uploaded);
* a sanitized public summary carrying only counts and digests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_DEFAULT = 20
CHILD_TIMEOUT_SECONDS = 60.0
_SYMBOL_PATTERN = re.compile(r"^fn_(\d{3})_(\d{4})$")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_order(symbols: list[str]) -> list[str]:
    """Deterministic risk-weighted interleave.

    Section 000 is the main (boot) section; other sections are overlays.
    Take overlay leaders (first two functions of every non-main section) and
    boot-boundary functions (main section in address order), alternating so
    both risk classes are exercised early.
    """

    by_section: dict[str, list[str]] = {}
    for symbol in symbols:
        match = _SYMBOL_PATTERN.match(symbol)
        if not match:
            continue
        by_section.setdefault(match.group(1), []).append(symbol)
    for section in by_section.values():
        section.sort()

    boot = list(by_section.get("000", []))
    overlay_leaders: list[str] = []
    for section_id in sorted(by_section):
        if section_id == "000":
            continue
        overlay_leaders.extend(by_section[section_id][:2])

    ordered: list[str] = []
    boot_iter = iter(boot)
    leader_iter = iter(overlay_leaders)
    while True:
        progressed = False
        for iterator in (leader_iter, boot_iter):
            try:
                ordered.append(next(iterator))
                progressed = True
            except StopIteration:
                pass
        if not progressed:
            return ordered


def _run_child(arguments: list[str]) -> tuple[int | None, str, str]:
    try:
        completed = subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            timeout=CHILD_TIMEOUT_SECONDS,
            check=False,
        )
        return completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired:
        return None, "", "timeout"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer", required=True, type=Path)
    parser.add_argument("--generated-root", required=True, type=Path)
    parser.add_argument("--target", type=int, default=TARGET_DEFAULT)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / "captures" / "private" / "phase5",
    )
    parser.add_argument(
        "--public-summary",
        type=Path,
        default=None,
        help="Sanitized public summary output (counts and digests only)",
    )
    arguments = parser.parse_args()

    if arguments.target < 20:
        print("target below the acceptance minimum of 20", file=sys.stderr)
        return 1
    inventory = json.loads(
        (arguments.generated_root / "symbol_inventory.json").read_text(
            encoding="utf-8"
        )
    )
    candidates = _candidate_order(inventory["normal_callable_symbols"])
    if not candidates:
        print("no candidates", file=sys.stderr)
        return 1

    blob_root = arguments.output_root / "blobs"
    blob_root.mkdir(parents=True, exist_ok=True)

    passed: list[dict[str, object]] = []
    excluded: list[dict[str, str]] = []
    for symbol in candidates:
        if len(passed) >= arguments.target:
            break
        blob_path = blob_root / f"{symbol}.jfgcap"
        code, stdout, stderr = _run_child(
            [str(arguments.producer), "--capture", symbol, str(blob_path)]
        )
        if code != 0:
            reason = "timeout" if code is None else f"exit-{code}"
            excluded.append({"function": symbol, "reason": reason})
            continue
        replay_code, _, replay_err = _run_child(
            [str(arguments.producer), "--replay", str(blob_path)]
        )
        if replay_code != 0:
            excluded.append(
                {"function": symbol, "reason": "cross-process-replay"}
            )
            continue
        fault_code, fault_out, fault_err = _run_child(
            [str(arguments.producer), "--seed-fault", str(blob_path)]
        )
        if fault_code != 0:
            excluded.append(
                {"function": symbol, "reason": "fault-localization"}
            )
            continue
        record = json.loads(stdout.strip().splitlines()[-1])
        record["blob_path"] = str(blob_path.relative_to(REPO_ROOT))
        record["fault_localization"] = fault_out.strip()
        passed.append(record)
        print(
            f"[{len(passed)}/{arguments.target}] {symbol} ok",
            flush=True,
        )

    ledger = {
        "schema_version": 1,
        "kind": "jfg-phase5-boundary-capture-ledger",
        "selection_policy": "boot-boundary-and-overlay-leaders-v1",
        "target": arguments.target,
        "passed": passed,
        "excluded": excluded,
        "generated_root_inventory_sha256": _sha256_file(
            arguments.generated_root / "symbol_inventory.json"
        ),
    }
    ledger_path = arguments.output_root / "boundary-capture-ledger.json"
    ledger_path.write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"ledger: {ledger_path} passed={len(passed)} "
          f"excluded={len(excluded)}")

    if arguments.public_summary is not None:
        ledger_bytes = ledger_path.read_bytes()
        summary = {
            "schema_version": 1,
            "kind": "jfg-phase5-boundary-capture-summary",
            "selection_policy": ledger["selection_policy"],
            "captured_functions": len(passed),
            "excluded_functions": len(excluded),
            "exclusion_reasons": sorted(
                {entry["reason"] for entry in excluded}
            ),
            "private_ledger_sha256": hashlib.sha256(
                ledger_bytes
            ).hexdigest(),
            "generated_root_inventory_sha256": ledger[
                "generated_root_inventory_sha256"
            ],
        }
        arguments.public_summary.parent.mkdir(parents=True, exist_ok=True)
        arguments.public_summary.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"public summary: {arguments.public_summary}")

    if len(passed) < arguments.target:
        print("boundary-capture target not met", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
