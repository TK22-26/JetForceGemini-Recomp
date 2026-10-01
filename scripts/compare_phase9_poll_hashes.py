"""Compare semantic game state at numbered controller-input poll boundaries.

The two poll hooks must be independently shown equivalent before this report
can establish gameplay parity. Matching input indices alone do not do that.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from scripts.build_phase9_route_replays import load_replay
from scripts.compare_phase9_retrace_hashes import describe_difference, validate_state
from scripts.phase95_bridge import digest


HEADER = {"kind": "jfg-phase9-poll-hash-header", "schema": 1,
          "boundary": "pre-controller-input"}
STATE_FIELDS = ("front_mode", "level_word", "rng_seed", "player_actor", "player_sha256",
                "actor_list", "actor_count", "actor_table_sha256",
                "globals_sha256", "camera_sha256", "actors")


def records(path: Path, side: str):
    if side not in ("native", "oracle"):
        raise ValueError("unsupported poll trace side")
    with path.open(encoding="utf-8") as stream:
        if json.loads(next(stream, "null")) != HEADER:
            raise ValueError(f"invalid poll hash header: {path}")
        expected = 0
        for line in stream:
            row = json.loads(line)
            if (not isinstance(row, dict) or
                    row.get("kind") != "jfg-phase9-poll-hash" or
                    row.get("schema") != 1 or type(row.get("poll")) is not int or
                    row["poll"] != expected):
                raise ValueError(f"invalid or missing poll {expected}: {path}")
            for key in ("connected", "buttons", "stick_x", "stick_y",
                        "level_word"):
                if type(row.get(key)) is not int:
                    raise ValueError(f"invalid {key} at poll {expected}: {path}")
            if type(row.get("update_counter_valid")) is not bool or (
                    row["update_counter_valid"] and
                    (type(row.get("completed_updates")) is not int or
                     row["completed_updates"] < 0)) or (
                    not row["update_counter_valid"] and
                    row.get("completed_updates") is not None):
                raise ValueError(f"invalid update-counter provenance at poll {expected}")
            if (row["connected"] not in (0, 1) or
                    not 0 <= row["buttons"] <= 0xFFFF or
                    not -128 <= row["stick_x"] <= 127 or
                    not -128 <= row["stick_y"] <= 127 or
                    not 0 <= row["level_word"] <= 0xFFFFFFFF):
                raise ValueError(f"out-of-range input or update at poll {expected}")
            clock = "vi_retraces" if side == "native" else "emulator_frame"
            if type(row.get(clock)) is not int or row[clock] < 0:
                raise ValueError(f"invalid {clock} at poll {expected}: {path}")
            validate_state(row)
            yield row
            expected += 1
        if expected == 0:
            raise ValueError(f"empty poll hash stream: {path}")


def producer_pins(source: Path, native: Path, oracle: Path,
                  manifest: dict, required: int) -> dict:
    native_result = native.parent / "native-result.json"
    oracle_result = oracle.parent / "oracle-result.json"
    if not native_result.is_file() and not oracle_result.is_file():
        return {"verified": False, "reason": "producer result manifests absent"}
    if not native_result.is_file() or not oracle_result.is_file():
        raise ValueError("only one poll producer result manifest is available")
    left = json.loads(native_result.read_text(encoding="utf-8"))
    right = json.loads(oracle_result.read_text(encoding="utf-8"))
    initial = manifest.get("initial_state") or {}
    rom = left.get("rom_sha256")
    if (left.get("kind") != "jfg-phase95-native-selected-poll-replay" or
            right.get("kind") != "jfg-phase95-oracle-poll-replay" or
            left.get("exit_code") != 0 or right.get("exit_code") != 0 or
            not left.get("probe_target_reached") or not right.get("trace_complete") or
            left.get("poll_semantic_hashes") is not True or
            right.get("poll_semantic_hashes") is not True or
            not left.get("poll_semantic_hash_trace_complete") or
            not right.get("poll_semantic_hash_trace_complete") or
            left.get("poll_semantic_hash_sha256") != digest(native) or
            right.get("poll_semantic_hash_sha256") != digest(oracle) or
            left.get("poll_semantic_hash_count", 0) < required or
            right.get("poll_semantic_hash_count", 0) < required or
            left.get("input_sha256") != manifest["input_sha256"] or
            right.get("input_sha256") != manifest["input_sha256"] or
            right.get("source_export_sha256") != digest(source / "export-manifest.json") or
            left.get("initial_flash_sha256") != initial.get("flash_sha256") or
            left.get("initial_pak_sha256") != initial.get("pak_sha256") or
            digest(source / "initial.flash") != initial.get("flash_sha256") or
            digest(source / "initial.pak") != initial.get("pak_sha256") or
            right.get("oracle_initial_flash_sha256") != initial.get("flash_sha256") or
            right.get("initial_flash_matches_candidate") is not True or
            not isinstance(rom, str) or not re.fullmatch("[0-9a-f]{64}", rom) or
            right.get("rom_sha256") != rom):
        raise ValueError("poll producer manifest or initial-state pin changed")
    return {"verified": True, "native_result_sha256": digest(native_result),
            "oracle_result_sha256": digest(oracle_result),
            "rom_sha256": rom,
            "native_executable_sha256": left.get("executable_sha256"),
            "emulator_sha256": right.get("emulator_sha256"),
            "initial_flash_matches_both": True,
            "native_pak_matches_candidate": True,
            "oracle_pak_equivalence": "not_verified"}


def compare(source: Path, native: Path, oracle: Path,
            *, prefix_polls: int | None = None) -> dict:
    source = source.resolve(strict=True)
    manifest = json.loads((source / "export-manifest.json").read_text(encoding="utf-8"))
    input_path = source / "controller.input"
    if (manifest.get("kind") != "jfg-phase95-selected-input-export" or
            manifest.get("input_sha256") != digest(input_path)):
        raise ValueError("selected input export changed or is unsupported")
    events = load_replay(input_path)
    declared = manifest.get("controller_polls")
    final = manifest.get("oracle_final_frame")
    if (type(declared) is not int or declared != len(events) or
            type(final) is not int or
            any(event.first != index or event.last != (
                final if index == declared - 1 else index + 1)
                for index, event in enumerate(events))):
        raise ValueError("poll comparison requires one selected sample per poll")
    if prefix_polls is not None and (type(prefix_polls) is not int or
                                     not 1 <= prefix_polls <= declared):
        raise ValueError("invalid poll prefix")
    required = declared if prefix_polls is None else prefix_polls
    pins = producer_pins(source, native, oracle, manifest, required)
    report = {"kind": "jfg-phase9-poll-semantic-comparison", "schema": 1,
              "acceptance": False, "alignment_validated": False,
              "parity_verified": False, "boundary": HEADER["boundary"],
              "input_sha256": manifest["input_sha256"],
              "source_export_sha256": digest(source / "export-manifest.json"),
              "native_trace_sha256": digest(native),
              "oracle_trace_sha256": digest(oracle),
              "producer_provenance": pins,
              "requested_polls": required, "compared_polls": 0,
              "input_prefix_match": False, "semantic_prefix_match": False,
              "first_input_mismatch": None, "first_semantic_mismatch": None,
              "first_clock_difference": None,
              "state_scan_complete": False, "mismatching_polls": 0,
              "mismatch_windows": 0, "longest_mismatch_window_polls": 0,
              "first_mismatch_windows": [], "first_reconvergence_poll": None,
              "caveat": "same poll index is diagnostic until hook phase and initial state are independently validated"}
    left, right = records(native, "native"), records(oracle, "oracle")
    window_start = None

    def close_window(last_poll: int, reconvergence: int | None) -> None:
        nonlocal window_start
        if window_start is None:
            return
        width = last_poll - window_start + 1
        report["mismatch_windows"] += 1
        report["longest_mismatch_window_polls"] = max(
            report["longest_mismatch_window_polls"], width)
        if len(report["first_mismatch_windows"]) < 8:
            report["first_mismatch_windows"].append({
                "first_poll": window_start, "last_poll": last_poll,
                "polls": width, "reconvergence_poll": reconvergence})
        if report["first_reconvergence_poll"] is None:
            report["first_reconvergence_poll"] = reconvergence
        window_start = None

    try:
        for poll in range(required):
            a, b = next(left, None), next(right, None)
            if a is None or b is None:
                report["first_input_mismatch"] = {
                    "poll": poll, "reason": "missing-poll",
                    "missing": "native" if a is None else "oracle"}
                return report
            event = events[poll]
            for side, row in (("native", a), ("oracle", b)):
                for key, expected in (("connected", event.connected),
                                      ("buttons", event.buttons),
                                      ("stick_x", event.stick_x),
                                      ("stick_y", event.stick_y)):
                    if row[key] != expected:
                        report["first_input_mismatch"] = {
                            "poll": poll, "side": side, "field": key,
                            "observed": row[key], "expected": expected}
                        return report
            report["compared_polls"] = poll + 1
            if report["first_clock_difference"] is None and \
                    a["vi_retraces"] != b["emulator_frame"]:
                report["first_clock_difference"] = {
                    "poll": poll, "native_vi_retraces": a["vi_retraces"],
                    "oracle_emulator_frame": b["emulator_frame"]}
            if any(a[key] != b[key] for key in STATE_FIELDS):
                report["mismatching_polls"] += 1
                if window_start is None:
                    window_start = poll
                if report["first_semantic_mismatch"] is None:
                    components, actors = describe_difference(a, b)
                    if a["level_word"] != b["level_word"]:
                        components.insert(1, "level_word")
                    report["first_semantic_mismatch"] = {
                        "poll": poll, "components": components,
                        "actor_differences": actors,
                        "native_completed_updates": a["completed_updates"],
                        "oracle_completed_updates": b["completed_updates"]}
            else:
                close_window(poll - 1, poll)
        close_window(required - 1, None)
        report["state_scan_complete"] = True
        report["input_prefix_match"] = True
        report["semantic_prefix_match"] = report["first_semantic_mismatch"] is None
        return report
    finally:
        left.close()
        right.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("native", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("--prefix-polls", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare(args.source, args.native, args.oracle,
                     prefix_polls=args.prefix_polls)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            parser.error("output already exists")
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["semantic_prefix_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
