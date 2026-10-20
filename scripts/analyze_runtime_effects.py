"""Summarize CPU-effect writes and audio queue age from a closed gameplay trace.

This reads optional gameplay.tsv logs, not normal support ZIPs. Draw calls and
compositor events are not proof of visible pixels or speaker latency. No game
files, ROM, saves or memory snapshots are read.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics
from typing import Iterable


def _distribution(values: list[float]) -> dict | None:
    if not values:
        return None
    ordered = sorted(values)
    return {
        "median": statistics.median(ordered),
        "p95": ordered[int(.95 * (len(ordered) - 1))],
        "p99": ordered[int(.99 * (len(ordered) - 1))],
        "maximum": ordered[-1],
    }


def analyze(lines: Iterable[str], *, from_seconds: float = 10.0) -> dict:
    if not math.isfinite(from_seconds) or from_seconds < 0:
        raise ValueError("analysis start must be nonnegative and finite")
    counts = Counter()
    effects = {
        name: {"calls": 0, "calls_with_changed_pixels": 0, "changed_pixels": 0}
        for name in ("rain", "reticle")
    }
    audio = []
    transitions = []
    previous_time = -1
    relevant = {"rain-pixel-output", "reticle-line-output", "audio-queue",
                "audio-start", "audio-underrun", "audio-pause-empty", "audio-resume",
                "audio-anchor-drain-begin", "audio-anchor-drain-end",
                "host-pause", "host-resume"}
    for number, line in enumerate(lines, 1):
        fields = line.rstrip("\r\n").split("\t")
        if fields[0] in ("", "jfg-gameplay-trace-v1"):
            continue
        if len(fields) < 2:
            raise ValueError(f"incomplete record on line {number}")
        if fields[1] not in relevant:
            continue
        try:
            timestamp = int(fields[0])
            values = [int(value, 16) for value in fields[2:]]
            if timestamp < 0 or any(value < 0 for value in values):
                raise ValueError("negative value")
            if timestamp < previous_time:
                raise ValueError("relevant timestamps went backwards")
        except ValueError as error:
            raise ValueError(f"invalid record on line {number}: {error}") from error
        previous_time = timestamp
        if timestamp < from_seconds * 1_000_000:
            continue
        event = fields[1]
        counts[event] += 1
        if event in ("rain-pixel-output", "reticle-line-output"):
            expected = 4 if event == "rain-pixel-output" else 3
            if len(values) != expected:
                raise ValueError(f"invalid pixel-write record on line {number}")
            effect = effects["rain" if event == "rain-pixel-output" else "reticle"]
            changed = values[-1]
            effect["calls"] += 1
            effect["calls_with_changed_pixels"] += int(changed > 0)
            effect["changed_pixels"] += changed
        elif event == "audio-queue":
            if len(values) != 5:
                raise ValueError(f"invalid audio record on line {number}")
            queued, total, consumed, frequency, playing = values
            if not 8000 <= frequency <= 96000 or playing not in (0, 1):
                raise ValueError(f"invalid audio format/state on line {number}")
            if total < consumed or total - consumed != queued:
                raise ValueError(f"inconsistent audio byte counters on line {number}")
            audio.append((timestamp / 1_000_000, queued * 1000 / (frequency * 4), playing))
        elif len(transitions) < 64:
            transitions.append({"time_s": timestamp / 1_000_000, "event": event,
                                "values": values})
    playing = [(time, age) for time, age, active in audio if active]
    minutes: dict[int, list[float]] = {}
    for time, age in playing:
        minutes.setdefault(int(time // 60), []).append(age)
    return {
        "from_seconds": from_seconds,
        "event_counts": dict(counts),
        "cpu_effects": effects,
        "audio": {
            "queue_samples": len(audio),
            "playing_samples": len(playing),
            "queue_ms_all_states": _distribution([age for _, age, _ in audio]),
            "queue_ms_playing": _distribution([age for _, age in playing]),
            "playing_samples_over_250ms": sum(age > 250 for _, age in playing),
            "playing_samples_over_1000ms": sum(age > 1000 for _, age in playing),
            "minute_medians_ms": {str(m): statistics.median(ages)
                                  for m, ages in sorted(minutes.items())},
            "largest_playing_queues": [
                {"time_s": time, "queue_ms": age}
                for time, age in sorted(playing, key=lambda row: row[1], reverse=True)[:8]
            ],
        },
        "transitions": transitions,
        "transitions_truncated": sum(counts[name] for name in relevant
            if name not in ("rain-pixel-output", "reticle-line-output", "audio-queue")) > len(transitions),
        "limits": [
            "No automatic pass/fail or trace-completeness claim.",
            "Zero pixel-writing calls do not verify an effect's presentation.",
            "Queue age excludes audio already handed to the backend or device.",
            "Missing events can mean their diagnostic probe was disabled.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="Closed session gameplay.tsv")
    parser.add_argument("--from-seconds", type=float, default=10.0,
                        help="Exclude startup by default; use 0 to include it")
    args = parser.parse_args()
    try:
        with args.trace.open(encoding="utf-8-sig") as source:
            result = analyze(source, from_seconds=args.from_seconds)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
