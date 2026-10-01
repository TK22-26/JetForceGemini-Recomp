"""Capture same-poll controller-return bytes in native and BizHawk.

This local producer never promotes matching bytes to parity or authorization
for a gameplay-code change. Completed sides are reused after a restart.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import phase95_native_replay, phase95_oracle_replay
from scripts.phase9_controller_return import compare, read
from scripts.phase9_event_trace import validate_windows
from scripts.phase9_poll_semantic_pair import (
    PRIVATE_ROOT, ROOT, _existing_side, _plan, write_json_atomic,
)
from scripts.phase95_bridge import digest, runtime_digest


KIND = "jfg-phase9-controller-return-pair"
CAPABILITY_MARKER = b"JFG_PHASE9_CONTROLLER_RETURN"


def native_capable(executable: Path) -> bool:
    tail = b""
    with Path(executable).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            joined = tail + chunk
            if CAPABILITY_MARKER in joined:
                return True
            tail = joined[-(len(CAPABILITY_MARKER) - 1):]
    return False


def _side(path: Path, side: str, plan: dict) -> dict | None:
    result = _existing_side(path, side, plan)
    if result is None:
        return None
    windows = tuple(tuple(window) for window in plan["event_windows"])
    trace = path / ("retrace-hashes.jsonl.controller-return.tsv"
                    if side == "native" else "controller-return.tsv")
    rows = read(trace, windows)
    if (result.get("event_windows") != plan["event_windows"] or
            result.get("event_trace_complete") is not True or
            result.get("controller_return_trace_complete") is not True or
            result.get("controller_return_rows") != len(rows) or
            result.get("controller_return_trace_sha256") != digest(trace) or
            (side == "native" and result.get("controller_return") is not True) or
            (side == "oracle" and (
                result.get("controller_return_pc") != plan["return_pc"] or
                result.get("vi_consumed_trace_complete") is not True))):
        raise ValueError(f"existing {side} controller-return trace changed")
    return result


def run(output: Path, source: Path, executable: Path, emulator: Path,
        rom: Path, rom_sha256: str, *, target: int,
        windows: tuple[tuple[int, int], ...], return_pc: int,
        timeout: int = 600) -> dict:
    output, source, executable, emulator, rom = (
        Path(value).resolve() for value in
        (output, source, executable, emulator, rom))
    private = PRIVATE_ROOT.resolve(strict=True)
    if (not output.is_relative_to(private) or output == private or
            output.is_relative_to(source) or source.is_relative_to(output) or
            output.is_relative_to(emulator.parent) or
            emulator.parent.is_relative_to(output)):
        raise ValueError("controller-return output must be disjoint and private")
    for path in (source, executable, emulator, rom):
        if not path.exists():
            raise ValueError(f"missing controller-return input: {path}")
    if not native_capable(executable):
        raise ValueError("native executable lacks controller-return trace support")
    windows = validate_windows(windows, poll_hashes=True,
                               update_hashes=True, vi_trace=True)
    if (not windows or type(return_pc) is not int or
            not 0x80000000 <= return_pc <= 0x803FFFFC or return_pc % 4):
        raise ValueError("controller-return window or caller PC is invalid")
    plan = _plan(source, executable, emulator, rom, rom_sha256, target, timeout)
    if windows[-1][1] >= target:
        raise ValueError("controller-return window exceeds target")
    plan.update(kind=KIND, event_windows=[list(window) for window in windows],
                return_pc=f"0x{return_pc:08x}",
                native_runtime_sha256=runtime_digest(executable.parent))
    plan["tool_sha256"].update({name: digest(ROOT / name) for name in (
        "scripts/phase9_controller_return_pair.py",
        "scripts/phase9_controller_return.py",
        "scripts/phase9_event_trace.py")})
    if output.exists():
        path = output / "plan.json"
        if (not path.is_file() or
                json.loads(path.read_text(encoding="utf-8")) != plan):
            raise ValueError("existing controller-return output has no matching plan")
    else:
        output.mkdir(parents=True)
        write_json_atomic(output / "plan.json", plan)
    native_dir, oracle_dir = output / "native", output / "oracle"
    if _side(native_dir, "native", plan) is None:
        phase95_native_replay.replay(
            source, native_dir, executable, rom, rom_sha256,
            target_retraces=target, timeout=timeout,
            update_hashes=True, poll_hashes=True, event_windows=windows,
            controller_return=True)
        _side(native_dir, "native", plan)
    if _side(oracle_dir, "oracle", plan) is None:
        phase95_oracle_replay.replay(
            oracle_dir, emulator, rom, rom_sha256, source,
            target_frame=target, timeout=timeout, vi_trace=True,
            update_hashes=True, poll_hashes=True, domain_inventory=True,
            event_windows=windows, controller_return_pc=return_pc)
        _side(oracle_dir, "oracle", plan)
    report = compare(
        native_dir / "retrace-hashes.jsonl.controller-return.tsv",
        oracle_dir / "controller-return.tsv", windows)
    report_path = output / "controller-return-report.json"
    if report_path.exists():
        if json.loads(report_path.read_text(encoding="utf-8")) != report:
            raise ValueError("existing controller-return report changed")
    else:
        write_json_atomic(report_path, report)
    result = {
        "kind": KIND, "schema": 1, "complete": True,
        "plan_sha256": digest(output / "plan.json"),
        "native_result_sha256": digest(native_dir / "native-result.json"),
        "oracle_result_sha256": digest(oracle_dir / "oracle-result.json"),
        "controller_return_report_sha256": digest(report_path),
        "shared_polls": report["shared_polls"],
        "matching_shared_poll_prefix": report["matching_shared_poll_prefix"],
        "first_same_poll_difference": report["first_same_poll_difference"],
        "alignment_validated": False, "parity_verified": False,
    }
    path = output / "pair-result.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != result:
            raise ValueError("existing controller-return pair result changed")
    else:
        write_json_atomic(path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
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
    print(json.dumps(run(args.output, args.source, args.executable,
                         args.emulator, args.rom, args.rom_sha256,
                         target=args.target, windows=windows,
                         return_pc=args.return_pc, timeout=args.timeout),
                     sort_keys=True))


if __name__ == "__main__":
    main()
