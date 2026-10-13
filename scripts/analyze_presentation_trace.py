"""Analyze displayed interpolation progress, independently of the FPS counter.

Input: optional JFG_RT64_INTERPOLATION_TRACE TSV, after a clean process exit.
Phase is expressed in guest VI units. Source cadence may change between samples.
This measures selected interpolation samples, not GPU pixels or monitor scanout.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Iterable


def analyze(lines: Iterable[str], *, first_vi: int = 0,
            last_vi: int | None = None, expected_fps: float | None = None) -> dict:
    if expected_fps is not None and (not math.isfinite(expected_fps) or expected_fps <= 0):
        raise ValueError("expected FPS must be positive and finite")
    samples = []
    for number, line in enumerate(lines, 1):
        fields = line.strip().split("\t")
        if fields[0] != "display":
            continue
        try:
            if len(fields) != 10:
                raise ValueError("expected ten fields")
            timestamp, tick, source, target, frame, count = map(int, fields[1:7])
            alpha = float(fields[7])
            if not math.isfinite(alpha) or not 0 <= alpha <= 1 or source < 0:
                raise ValueError("invalid source rate or interpolation weight")
        except ValueError as error:
            raise ValueError(f"invalid display record on line {number}: {error}") from error
        if source == 0 or tick < first_vi or (last_vi is not None and tick >= last_vi):
            continue
        # The previous endpoint is one *actual source interval* before this tick.
        # Assuming two VIs misclassifies valid 20-Hz interpolation as jumps.
        phase = tick - (60.0 / source) * (1.0 - alpha)
        samples.append((timestamp, phase))
    steps = [b[1] - a[1] for a, b in zip(samples, samples[1:])]
    intervals = [(b[0] - a[0]) / 1000 for a, b in zip(samples, samples[1:])]
    epsilon = 0.0001  # TSV weights have six significant digits.
    result = {
        "samples": len(samples),
        "repeated_phases": sum(abs(step) <= epsilon for step in steps),
        "backward_phases": sum(step < -epsilon for step in steps),
        "phase_step_counts": dict(Counter(f"{step:.4f}" for step in steps)),
        "present_interval_ms": None,
    }
    if intervals:
        ordered = sorted(intervals)
        result["present_interval_ms"] = {
            "median": statistics.median(intervals),
            "p99": ordered[int(0.99 * (len(ordered) - 1))],
            "maximum": max(intervals),
        }
    if expected_fps is not None:
        expected = 60.0 / expected_fps
        result["expected_phase_step"] = expected
        result["uneven_phase_steps"] = sum(abs(step - expected) > epsilon for step in steps)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--from-vi", type=int, default=0)
    parser.add_argument("--to-vi", type=int)
    parser.add_argument("--expected-fps", type=float,
                        help="Effective capped rate, accounting for VSync; omit for Unlimited")
    args = parser.parse_args()
    try:
        with args.trace.open(encoding="utf-8") as source:
            result = analyze(source, first_vi=args.from_vi, last_vi=args.to_vi,
                             expected_fps=args.expected_fps)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))
    return 0 if result["samples"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
