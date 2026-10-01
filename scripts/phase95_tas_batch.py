#!/usr/bin/env python3
"""Run restartable, bounded JP TAS capture segments in private storage.

One invocation runs sequentially through the movie. Existing failed attempts
are never deleted; a restart creates the next attempt directory for that same
segment. Only complete segments with the current source pins may be skipped.
Do not point the output root inside the source emulator directory.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from scripts import phase95_tas_capture as capture_module


KIND = "jfg-phase95-jp-tas-capture-batch"
SCHEMA = 1
EXPECTED_MOVIE_FRAMES = 638_477
EXPECTED_MOVIE_SHA256 = "e368d9256caaa9a432645febf7110ae193fd929b521283656962506d13848b9f"


class BatchError(RuntimeError):
    """A batch plan, existing artifact, or capture attempt is unsafe."""


def _write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise BatchError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise BatchError(f"not a JSON object: {path}")
    return value


def _pins(emulator: Path, rom: Path, movie: Path) -> dict[str, Any]:
    if emulator.name.lower() != "emuhawk.exe" or not emulator.is_file():
        raise BatchError("source emulator must be EmuHawk.exe")
    if not rom.is_file() or not movie.is_file():
        raise BatchError("ROM and direct BK2 movie must be files")
    movie_info = capture_module.inspect_movie(movie)
    if (movie_info["frames"] != EXPECTED_MOVIE_FRAMES or
            movie_info["movie_sha256"].lower() != EXPECTED_MOVIE_SHA256):
        raise BatchError("movie is not the pinned 638477-frame TAS BK2")
    if capture_module.sha1(rom) != capture_module.JP_ROM_SHA1:
        raise BatchError("ROM SHA-1 does not match the Japanese TAS")
    rom_sha256 = capture_module.digest(rom)
    emulator_sha256 = capture_module.digest(emulator)
    runtime_sha256 = capture_module.runtime_digest(emulator.parent)
    if rom_sha256 != capture_module.JP_ROM_SHA256:
        raise BatchError("ROM SHA-256 does not match the synchronized TAS")
    if (emulator_sha256 != capture_module.BIZHAWK_291_EXE_SHA256 or
            runtime_sha256 != capture_module.BIZHAWK_291_RUNTIME_SHA256):
        raise BatchError("emulator runtime does not match synchronized BizHawk 2.9.1")
    script = Path(capture_module.__file__).with_suffix(".lua").resolve()
    if not script.is_file():
        raise BatchError("TAS capture Lua script is missing")
    return {
        "rom_sha1": capture_module.JP_ROM_SHA1,
        "rom_sha256": rom_sha256,
        "movie_sha256": movie_info["movie_sha256"],
        "movie_frames": movie_info["frames"],
        "emulator_sha256": emulator_sha256,
        "runtime_sha256": runtime_sha256,
        "script_sha256": capture_module.digest(script),
    }


def _segments(frame_count: int, segment_frames: int):
    for first in range(0, frame_count, segment_frames):
        yield first, min(first + segment_frames, frame_count) - 1


def _complete_attempt(segment: Path, first: int, last: int,
                      pins: dict[str, Any], previous: Path | None) -> Path | None:
    parent_hash = (_read_json(previous / "result.json")["continuation_sha256"]
                   if previous is not None else None)
    parent_path = str(previous) if previous is not None else None
    attempts = sorted(segment.glob("attempt-*")) if segment.exists() else []
    complete: list[Path] = []
    for attempt in attempts:
        if not attempt.is_dir():
            raise BatchError(f"unexpected non-directory attempt: {attempt}")
        result_path = attempt / "result.json"
        if not result_path.is_file():
            continue  # Interrupted or failed before the result was written.
        result = _read_json(result_path)
        if result.get("complete") is not True:
            continue
        if result.get("first") != first or result.get("last") != last:
            raise BatchError(f"completed attempt has wrong frame range: {attempt}")
        if ("parent_continuation_sha256" not in result or
                result.get("resume_from") != parent_path or
                result["parent_continuation_sha256"] != parent_hash):
            raise BatchError(f"completed attempt has wrong parent lineage: {attempt}")
        for key, expected in pins.items():
            if result.get(key) != expected:
                raise BatchError(f"completed attempt has changed {key}: {attempt}")
        try:
            capture_module.validate_resume(attempt, pins, last + 1)
            capture_module.parse_trace(attempt / "frames.tsv", first, last)
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise BatchError(f"completed attempt failed revalidation: {attempt}: {error}") from error
        complete.append(attempt)
    if len(complete) > 1:
        raise BatchError(f"multiple complete attempts for {segment}")
    return complete[0] if complete else None


def _next_attempt(segment: Path) -> Path:
    segment.mkdir(parents=True, exist_ok=True)
    attempts = list(segment.iterdir())
    if any(not item.is_dir() or not item.name.startswith("attempt-") or
           not item.name[8:].isdigit() for item in attempts):
        raise BatchError(f"unexpected file in segment directory: {segment}")
    number = max((int(item.name[8:]) for item in attempts), default=-1) + 1
    if number > 9999:
        raise BatchError("too many attempts for one segment")
    return segment / f"attempt-{number:04d}"


def run_batch(root: Path, emulator: Path, rom: Path, movie: Path, *,
              segment_frames: int = 20_000, interval: int = 10_000,
              timeout: int = 3600, full_rdram: bool = False) -> dict[str, Any]:
    """Capture the complete movie, resuming only revalidated pinned segments."""
    root, emulator, rom, movie = (Path(path).resolve() for path in
                                  (root, emulator, rom, movie))
    if not 1 <= segment_frames <= capture_module.MAX_SEGMENT_FRAMES:
        raise BatchError("segment_frames exceeds the bounded capture limit")
    if not 1 <= interval <= segment_frames or timeout < 1:
        raise BatchError("invalid checkpoint interval or timeout")
    if root == emulator.parent or emulator.parent in root.parents:
        raise BatchError("batch output cannot be inside the source emulator directory")
    pins = _pins(emulator, rom, movie)
    frame_count = pins["movie_frames"]
    if frame_count < 1:
        raise BatchError("movie contains no input frames")
    plan = {
        "kind": KIND, "schema": SCHEMA,
        "source_emulator": str(emulator), "source_rom": str(rom),
        "source_movie": str(movie), "pins": pins,
        "driver_sha256": capture_module.digest(Path(capture_module.__file__).resolve()),
        "batch_sha256": capture_module.digest(Path(__file__).resolve()),
        "segment_frames": segment_frames, "checkpoint_interval": interval,
        "timeout": timeout, "full_rdram": full_rdram,
        "semantic_status": "raw-unverified-jp",
    }
    if root.exists():
        if not root.is_dir() or not (root / "batch.json").is_file():
            raise BatchError("existing batch root has no batch.json; refusing to overwrite")
        if _read_json(root / "batch.json") != plan:
            raise BatchError("batch plan or pinned source files changed")
    else:
        root.mkdir(parents=True)
        _write_json(root / "batch.json", plan)

    previous: Path | None = None
    completed = 0
    total_segments = (frame_count + segment_frames - 1) // segment_frames
    for first, last in _segments(frame_count, segment_frames):
        segment = root / "segments" / f"segment-{first:06d}-{last:06d}"
        prior_complete = _complete_attempt(segment, first, last, pins, previous)
        if prior_complete is not None:
            previous = prior_complete
            completed += 1
            continue
        attempt = _next_attempt(segment)
        print(json.dumps({"starting": [first, last], "attempt": str(attempt)}), flush=True)
        try:
            result = capture_module.capture(
                attempt, emulator, rom, movie, first=first, last=last,
                interval=interval, resume_from=previous, timeout=timeout,
                full_rdram=full_rdram,
            )
            if result.get("complete") is not True:
                raise BatchError("capture returned an incomplete result")
            verified = _complete_attempt(segment, first, last, pins, previous)
            if verified != attempt:
                raise BatchError("newly captured segment did not revalidate")
        except Exception as error:
            summary = {"kind": KIND, "schema": SCHEMA, "complete": False,
                       "movie_frames": frame_count, "segments_total": total_segments,
                       "segments_complete": completed,
                       "failed_segment": [first, last],
                       "failed_attempt": str(attempt), "error": str(error)}
            _write_json(root / "batch-result.json", summary)
            raise BatchError(f"stopped at {attempt}; prior attempts preserved: {error}") from error
        previous = attempt
        completed += 1
        _write_json(root / "batch-result.json", {
            "kind": KIND, "schema": SCHEMA, "complete": False,
            "movie_frames": frame_count, "segments_total": total_segments,
            "segments_complete": completed, "last_complete_frame": last,
        })
    summary = {"kind": KIND, "schema": SCHEMA, "complete": True,
               "movie_frames": frame_count, "segments_total": total_segments,
               "segments_complete": completed, "last_complete_frame": frame_count - 1}
    _write_json(root / "batch-result.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--movie", type=Path, required=True)
    parser.add_argument("--segment-frames", type=int, default=20_000)
    parser.add_argument("--interval", type=int, default=10_000)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--full-rdram", action="store_true")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run_batch(
            args.output, args.emulator, args.rom, args.movie,
            segment_frames=args.segment_frames, interval=args.interval,
            timeout=args.timeout, full_rdram=args.full_rdram,
        ), indent=2))
    except (BatchError, OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
