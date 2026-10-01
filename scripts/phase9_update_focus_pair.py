"""Replay the first divergent update with bounded game-visible input snapshots.

This is a local diagnostic producer. It does not infer initial Controller Pak
equivalence or promote an update-state mismatch to a guest-code bug.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts import phase95_native_replay, phase95_oracle_replay
from scripts.phase9_poll_semantic_pair import (
    PRIVATE_ROOT, ROOT, _existing_side, _plan, write_json_atomic,
)
from scripts.phase95_bridge import digest
from scripts.phase9_update_alignment import analyze as analyze_updates


KIND = "jfg-phase9-update-focus-input-pair"
SNAPSHOT_BYTES = 4 * 1024 * 1024
FIELDS = {
    "controller_current": (0xFB0C0, 24),
    "controller_previous": (0xFB0D8, 24),
    "buttons_pressed": (0xFB0F0, 8),
    "buttons_released": (0xFB0F8, 8),
}


def focus_range(update_alignment: dict) -> tuple[int, int]:
    difference = update_alignment.get("first_semantic_difference")
    if (not isinstance(difference, dict) or
            difference.get("reason") != "state-difference" or
            type(difference.get("update")) is not int or
            difference["update"] < 3 or
            update_alignment.get("matching_update_prefix") !=
            difference["update"] - 1 or
            update_alignment.get("alignment_validated") is not False or
            update_alignment.get("parity_verified") is not False):
        raise ValueError("no bounded first divergent update in the predecessor")
    update = difference["update"]
    return update - 2, update + 1


def verified_alignment_sha(path: Path, alignment: dict,
                           pinned_sha256: str | None) -> str:
    """Accept the producer's pinned JSON across LF/CRLF host conventions."""
    path = Path(path)
    if path.is_file():
        actual_sha256 = digest(path)
        if (pinned_sha256 != actual_sha256 or
                json.loads(path.read_text(encoding="utf-8")) != alignment):
            raise ValueError("event-pair update alignment changed")
        return actual_sha256
    if pinned_sha256 is not None:
        raise ValueError("event-pair update alignment is missing")
    encoded = (json.dumps(alignment, sort_keys=True, indent=2) +
               "\n").encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def snapshot_fields(path: Path) -> dict:
    path = Path(path)
    if not path.is_file() or path.stat().st_size != SNAPSHOT_BYTES:
        raise ValueError(f"missing or incomplete focused RDRAM snapshot: {path}")
    with path.open("rb") as stream:
        return {name: _read_field(stream, offset, length)
                for name, (offset, length) in FIELDS.items()}


def _read_field(stream, offset: int, length: int) -> str:
    stream.seek(offset)
    value = stream.read(length)
    if len(value) != length:
        raise ValueError("focused RDRAM field is incomplete")
    return value.hex()


def compare_snapshots(native_dir: Path, oracle_dir: Path,
                      first: int, last: int) -> dict:
    if not 1 <= first <= last or last - first > 15:
        raise ValueError("focused update interval is invalid")
    rows = []
    first_difference = None
    for update in range(first, last + 1):
        paths = [Path(side) / f"focus-update-{update}.rdram"
                 for side in (native_dir, oracle_dir)]
        fields = [snapshot_fields(path) for path in paths]
        different = [name for name in FIELDS
                     if fields[0][name] != fields[1][name]]
        if different and first_difference is None:
            first_difference = update
        rows.append({
            "update": update,
            "native_snapshot_sha256": digest(paths[0]),
            "oracle_snapshot_sha256": digest(paths[1]),
            "differing_fields": different,
            "native": fields[0], "oracle": fields[1],
        })
    return {
        "kind": "jfg-phase9-update-focus-input-comparison", "schema": 1,
        "first_update": first, "last_update": last,
        "first_input_buffer_difference_update": first_difference,
        "rows": rows, "alignment_validated": False, "parity_verified": False,
        "caveat": "Matching game-visible buffers do not prove identical Pak "
                  "state, VI scheduling, or all input reads within a call.",
    }


def _side(path: Path, side: str, plan: dict) -> dict | None:
    result = _existing_side(path, side, plan)
    if result is None:
        return None
    focus = tuple(plan["focus_updates"])
    if (result.get("focused_update_capture_complete") is not True or
            tuple(result.get("focused_update_range") or ()) != focus or
            (side == "oracle" and
             result.get("vi_consumed_trace_complete") is not True)):
        raise ValueError(f"existing {side} focus capture does not match plan")
    for update in range(focus[0], focus[1] + 1):
        snapshot_fields(path / f"focus-update-{update}.rdram")
    return result


def run(output: Path, event_pair: Path, *, timeout: int = 600) -> dict:
    output, event_pair = Path(output).resolve(), Path(event_pair).resolve(
        strict=True)
    private = PRIVATE_ROOT.resolve(strict=True)
    if (not output.is_relative_to(private) or output == private or
            not event_pair.is_relative_to(private) or
            event_pair == private or output.is_relative_to(event_pair) or
            event_pair.is_relative_to(output)):
        raise ValueError("focus output and predecessor must be disjoint private roots")
    predecessor_plan = json.loads((event_pair / "plan.json").read_text(
        encoding="utf-8"))
    predecessor_result = json.loads((event_pair / "pair-result.json").read_text(
        encoding="utf-8"))
    alignment_path = event_pair / "update-alignment.json"
    alignment = analyze_updates(
        event_pair / "native" / "retrace-hashes.jsonl.updates.jsonl",
        event_pair / "oracle" / "update-hashes.jsonl")
    alignment_sha256 = verified_alignment_sha(
        alignment_path, alignment,
        predecessor_result.get("update_alignment_sha256"))
    if (predecessor_plan.get("kind") != "jfg-phase9-event-order-pair" or
            predecessor_result.get("kind") != predecessor_plan["kind"] or
            predecessor_result.get("complete") is not True or
            predecessor_result.get("plan_sha256") != digest(
                event_pair / "plan.json") or
            alignment.get("kind") != "jfg-phase9-update-alignment" or
            alignment.get("native_sha256") != digest(
                event_pair / "native" /
                "retrace-hashes.jsonl.updates.jsonl") or
            alignment.get("oracle_sha256") != digest(
                event_pair / "oracle" / "update-hashes.jsonl")):
        raise ValueError("event-pair predecessor is incomplete or changed")
    first, last = focus_range(alignment)
    source, executable, emulator, rom = (
        Path(predecessor_plan[key]).resolve(strict=True) for key in
        ("source_export", "native_executable", "emulator", "rom"))
    target = predecessor_plan["target"]
    if (last >= target or type(timeout) is not int or
            not 1 <= timeout <= 3600 or
            output.is_relative_to(source) or source.is_relative_to(output) or
            output.is_relative_to(emulator.parent) or
            emulator.parent.is_relative_to(output)):
        raise ValueError("focus target, timeout, or output path is invalid")
    plan = _plan(source, executable, emulator, rom,
                 predecessor_plan["rom_sha256"], target, timeout)
    plan.update(kind=KIND, predecessor=str(event_pair),
                predecessor_plan_sha256=digest(event_pair / "plan.json"),
                predecessor_result_sha256=digest(event_pair / "pair-result.json"),
                predecessor_alignment_sha256=alignment_sha256,
                focus_updates=[first, last])
    plan["tool_sha256"].update({name: digest(ROOT / name) for name in (
        "scripts/phase9_update_focus_pair.py",
        "scripts/phase9_update_alignment.py")})
    if output.exists():
        if (not (output / "plan.json").is_file() or
                json.loads((output / "plan.json").read_text(
                    encoding="utf-8")) != plan):
            raise ValueError("existing focus output has no matching plan")
    else:
        output.mkdir(parents=True)
        write_json_atomic(output / "plan.json", plan)
    native_dir, oracle_dir = output / "native", output / "oracle"
    if _side(native_dir, "native", plan) is None:
        phase95_native_replay.replay(
            source, native_dir, executable, rom, plan["rom_sha256"],
            target_retraces=target, timeout=timeout, poll_hashes=True,
            update_hashes=True, focus_updates=(first, last))
        _side(native_dir, "native", plan)
    if _side(oracle_dir, "oracle", plan) is None:
        phase95_oracle_replay.replay(
            oracle_dir, emulator, rom, plan["rom_sha256"], source,
            target_frame=target, timeout=timeout, vi_trace=True,
            poll_hashes=True, update_hashes=True, domain_inventory=True,
            focus_updates=(first, last))
        _side(oracle_dir, "oracle", plan)
    report = compare_snapshots(native_dir, oracle_dir, first, last)
    report_path = output / "focus-input-report.json"
    if report_path.exists():
        if json.loads(report_path.read_text(encoding="utf-8")) != report:
            raise ValueError("existing focus input report changed")
    else:
        write_json_atomic(report_path, report)
    result = {
        "kind": KIND, "schema": 1, "complete": True,
        "plan_sha256": digest(output / "plan.json"),
        "native_result_sha256": digest(native_dir / "native-result.json"),
        "oracle_result_sha256": digest(oracle_dir / "oracle-result.json"),
        "focus_input_report_sha256": digest(report_path),
        "first_update": first, "last_update": last,
        "first_input_buffer_difference_update": report[
            "first_input_buffer_difference_update"],
        "alignment_validated": False, "parity_verified": False,
    }
    result_path = output / "pair-result.json"
    if result_path.exists():
        if json.loads(result_path.read_text(encoding="utf-8")) != result:
            raise ValueError("existing focus pair result changed")
    else:
        write_json_atomic(result_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--event-pair", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.event_pair, timeout=args.timeout),
                     sort_keys=True))


if __name__ == "__main__":
    main()
