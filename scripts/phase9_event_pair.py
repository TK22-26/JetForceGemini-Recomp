"""Capture a bounded, restartable native/BizHawk controller-event pair.

This producer runs locally without an AI model. Its report is diagnostic only:
no input shifting, initial-Pak equivalence, or parity is inferred from it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import phase95_native_replay, phase95_oracle_replay
from scripts.compare_phase9_poll_hashes import compare
from scripts.phase9_event_trace import analyze, read, validate_windows
from scripts.phase9_controller_callers import analyze as analyze_callers
from scripts.phase9_update_alignment import analyze as analyze_updates
from scripts.phase9_poll_semantic_pair import (
    PRIVATE_ROOT, ROOT, _existing_side, _plan, write_json_atomic,
)
from scripts.phase95_bridge import digest


KIND = "jfg-phase9-event-order-pair"


def _event_side(path: Path, side: str, plan: dict) -> dict | None:
    result = _existing_side(path, side, plan)
    if result is None:
        return None
    windows = tuple(tuple(window) for window in plan["event_windows"])
    trace = (path / "retrace-hashes.jsonl.events.tsv" if side == "native"
             else path / "events.tsv")
    if (result.get("event_windows") != [list(window) for window in windows] or
            result.get("event_trace_complete") is not True or
            result.get("event_trace_rows") != len(read(trace, windows, side)) or
            (side == "oracle" and (result.get("vi_consumed_trace") is not True or
                                    result.get("vi_consumed_trace_complete") is not True or
                                    result.get("controller_caller_trace_complete") is not True or
                                    result.get("controller_caller_trace_sha256") !=
                                    digest(path / "controller-callers.tsv")))):
        raise ValueError(f"existing {side} event trace does not match pair plan")
    return result


def run(output: Path, source: Path, executable: Path, emulator: Path,
        rom: Path, rom_sha256: str, *, target: int, timeout: int = 600,
        event_windows=((13, 21), (566, 577))) -> dict:
    output, source, executable, emulator, rom = (
        Path(value).resolve() for value in
        (output, source, executable, emulator, rom))
    private = PRIVATE_ROOT.resolve(strict=True)
    if not output.is_relative_to(private) or output == private:
        raise ValueError("event pair output must be under tools/private")
    if (output.is_relative_to(source) or source.is_relative_to(output) or
            output.is_relative_to(emulator.parent) or
            emulator.parent.is_relative_to(output)):
        raise ValueError("event pair output must be disjoint from inputs")
    if not source.is_dir():
        raise ValueError(f"missing event pair source: {source}")
    for path in (executable, emulator, rom):
        if not path.is_file():
            raise ValueError(f"missing event pair input: {path}")
    windows = validate_windows(event_windows, poll_hashes=True,
                               update_hashes=True)
    if not windows:
        raise ValueError("event pair needs at least one window")
    plan = _plan(source, executable, emulator, rom, rom_sha256, target, timeout)
    plan["kind"] = KIND
    plan["event_windows"] = windows
    plan["tool_sha256"].update({name: digest(ROOT / name) for name in (
        "scripts/phase9_event_pair.py", "scripts/phase9_event_trace.py",
        "scripts/phase9_controller_callers.py",
        "scripts/phase9_update_alignment.py",
        "scripts/compare_phase9_update_hashes.py")})
    if output.exists():
        path = output / "plan.json"
        if not path.is_file() or json.loads(path.read_text(
                encoding="utf-8")) != json.loads(json.dumps(plan)):
            raise ValueError("existing event pair output has no matching plan")
    else:
        output.mkdir(parents=True)
        write_json_atomic(output / "plan.json", plan)
    native_dir, oracle_dir = output / "native", output / "oracle"
    native = _event_side(native_dir, "native", plan)
    if native is None:
        phase95_native_replay.replay(
            source, native_dir, executable, rom, rom_sha256,
            target_retraces=target, timeout=timeout, poll_hashes=True,
            update_hashes=True, event_windows=windows)
        native = _event_side(native_dir, "native", plan)
    oracle = _event_side(oracle_dir, "oracle", plan)
    if oracle is None:
        phase95_oracle_replay.replay(
            oracle_dir, emulator, rom, rom_sha256, source,
            target_frame=target, timeout=timeout, vi_trace=True,
            poll_hashes=True, update_hashes=True, domain_inventory=True,
            event_windows=windows)
        oracle = _event_side(oracle_dir, "oracle", plan)
    prefix = min(native["poll_semantic_hash_count"],
                 oracle["poll_semantic_hash_count"])
    if prefix <= max(last for _, last in windows):
        raise ValueError("event windows exceed paired poll prefix")
    comparison = compare(
        source, native_dir / "retrace-hashes.jsonl.polls.jsonl",
        oracle_dir / "poll-hashes.jsonl", prefix_polls=prefix)
    if (comparison["producer_provenance"].get("verified") is not True or
            comparison["state_scan_complete"] is not True or
            comparison["input_prefix_match"] is not True):
        raise ValueError("event pair poll provenance is incomplete")
    report = analyze(native_dir / "retrace-hashes.jsonl.events.tsv",
                     oracle_dir / "events.tsv", windows)
    caller_report = analyze_callers(oracle_dir / "controller-callers.tsv",
                                    windows)
    if report["first_input_mismatch_poll"] is not None:
        raise ValueError("event trace input differs despite poll comparison")
    update_alignment = analyze_updates(
        native_dir / "retrace-hashes.jsonl.updates.jsonl",
        oracle_dir / "update-hashes.jsonl")
    for name, value in (("comparison.json", comparison),
                        ("event-report.json", report),
                        ("controller-caller-report.json", caller_report),
                        ("update-alignment.json", update_alignment)):
        path = output / name
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != json.loads(
                    json.dumps(value)):
                raise ValueError(f"existing {name} changed")
        else:
            write_json_atomic(path, value)
    summary = {
        "kind": KIND, "schema": 1, "complete": True,
        "alignment_validated": False, "parity_verified": False,
        "plan_sha256": digest(output / "plan.json"),
        "native_result_sha256": digest(native_dir / "native-result.json"),
        "oracle_result_sha256": digest(oracle_dir / "oracle-result.json"),
        "comparison_sha256": digest(output / "comparison.json"),
        "event_report_sha256": digest(output / "event-report.json"),
        "controller_caller_report_sha256": digest(
            output / "controller-caller-report.json"),
        "controller_caller_trace_sha256": caller_report["trace_sha256"],
        "update_alignment_sha256": digest(output / "update-alignment.json"),
        "native_event_trace_sha256": report["native_trace_sha256"],
        "oracle_event_trace_sha256": report["oracle_trace_sha256"],
        "shared_polls": prefix,
        "first_semantic_mismatch": comparison["first_semantic_mismatch"],
        "first_update_state_difference": update_alignment[
            "first_semantic_difference"],
        "matching_update_prefix": update_alignment["matching_update_prefix"],
        "first_event_interval_difference": (
            report["interval_differences"][0]
            if report["interval_differences"] else None),
        "native_pak_equivalence_validated": False,
        "reason_not_parity": report["caveat"],
    }
    result_path = output / "pair-result.json"
    if result_path.exists():
        if json.loads(result_path.read_text(encoding="utf-8")) != summary:
            raise ValueError("existing event pair result changed")
    else:
        write_json_atomic(result_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--target", type=int, default=1500)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--window", action="append", default=[],
                        metavar="FIRST:LAST")
    args = parser.parse_args()
    try:
        windows = [tuple(map(int, value.split(":")))
                   for value in args.window] if args.window else ((13, 21),
                                                                    (566, 577))
    except ValueError as error:
        parser.error(f"invalid --window: {error}")
    print(json.dumps(run(args.output, args.source, args.executable,
                         args.emulator, args.rom, args.rom_sha256,
                         target=args.target, timeout=args.timeout,
                         event_windows=windows), sort_keys=True))


if __name__ == "__main__":
    main()
