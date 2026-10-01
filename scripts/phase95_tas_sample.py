"""Capture one arbitrary Japanese TAS frame from a sealed batch predecessor.

The source batch is read-only. A sample gets a new private output directory,
its own isolated emulator process, and an offline full-RDRAM extraction.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import phase95_tas_batch as batch
from scripts import phase95_tas_capture as capture
from scripts import phase95_tas_state_batch as state_batch
from scripts import phase95_tas_state_extract as state_extract


PRIVATE_ROOT = Path(__file__).resolve().parents[1] / "tools" / "private"
KIND = "jfg-phase95-jp-tas-frame-sample"


def select_predecessor(root: Path, plan: dict, target: int) -> Path | None:
    """Return the nearest contiguous sealed batch segment ending before target."""
    previous = None
    for first, last in batch._segments(plan["pins"]["movie_frames"],
                                       plan["segment_frames"]):
        if last >= target:
            break
        segment = root / "segments" / f"segment-{first:06d}-{last:06d}"
        complete = batch._complete_attempt(segment, first, last,
                                           plan["pins"], previous)
        if complete is None:
            raise ValueError(f"missing sealed predecessor before frame {target}: {segment}")
        previous = complete
    return previous


def sample(output: Path, batch_root: Path, target: int, *,
           interval: int = 5000, timeout: int = 3600) -> dict:
    output, batch_root = Path(output).resolve(), Path(batch_root).resolve()
    private = PRIVATE_ROOT.resolve()
    if not output.is_relative_to(private) or not batch_root.is_relative_to(private):
        raise ValueError("sample and source batch must remain under tools/private")
    if output == batch_root or output.is_relative_to(batch_root):
        raise ValueError("sample output cannot modify the running batch root")
    if output.exists():
        raise FileExistsError(output)
    plan = state_batch.validate_plan(batch_root)
    if type(target) is not int or not 0 <= target < plan["pins"]["movie_frames"]:
        raise ValueError("target frame is outside pinned movie")
    if type(interval) is not int or not 1 <= interval <= capture.MAX_SEGMENT_FRAMES or \
            type(timeout) is not int or timeout < 1:
        raise ValueError("invalid bounded sample interval or timeout")
    emulator = Path(plan["source_emulator"]).resolve()
    rom = Path(plan["source_rom"]).resolve()
    movie = Path(plan["source_movie"]).resolve()
    if output == emulator.parent or output.is_relative_to(emulator.parent):
        raise ValueError("sample output cannot be inside the source emulator")
    if batch._pins(emulator, rom, movie) != plan["pins"] or \
            capture.digest(Path(capture.__file__).resolve()) != plan["driver_sha256"] or \
            capture.digest(Path(batch.__file__).resolve()) != plan["batch_sha256"]:
        raise ValueError("batch source or driver pins changed")
    prior = select_predecessor(batch_root, plan, target)
    first = (batch._read_json(prior / "result.json")["last"] + 1
             if prior is not None else 0)
    if not 1 <= target - first + 1 <= capture.MAX_SEGMENT_FRAMES:
        raise ValueError("sample exceeds one bounded capture segment")
    output.mkdir(parents=True)
    request = {"kind": KIND, "schema": 1, "target_frame": target,
               "capture_first": first, "semantic_status": "raw-unverified-jp",
               "sampler_sha256": capture.digest(Path(__file__).resolve()),
               "capture_driver_sha256": plan["driver_sha256"],
               "capture_lua_sha256": plan["pins"]["script_sha256"],
               "source_batch": str(batch_root),
               "source_batch_plan_sha256": capture.digest(batch_root / "batch.json"),
               "sealed_predecessor": str(prior) if prior is not None else None,
               "sealed_predecessor_sha256":
                   batch._read_json(prior / "result.json")["continuation_sha256"]
                   if prior is not None else None,
               "interval": interval, "timeout": timeout}
    (output / "sample-request.json").write_text(json.dumps(request, indent=2) + "\n")
    try:
        captured = capture.capture(output / "capture", emulator, rom, movie,
                                   first=first, last=target, interval=interval,
                                   resume_from=prior, timeout=timeout)
        if (captured.get("complete") is not True or
                captured.get("first") != first or captured.get("last") != target or
                captured.get("resume_from") != (str(prior) if prior else None) or
                captured.get("parent_continuation_sha256") !=
                    request["sealed_predecessor_sha256"]):
            raise ValueError("sample capture result has wrong range or lineage")
        extracted = state_extract.extract(output / "capture")
        if extracted.get("frame") != target or \
                extracted.get("semantic_status") != "raw-unverified-jp":
            raise ValueError("sample RDRAM extraction has wrong frame or schema")
        result = {**request, "complete": True,
                  "capture_result_sha256": capture.digest(output / "capture" / "result.json"),
                  "continuation_sha256": captured["continuation_sha256"],
                  "rdram_sha256": extracted["rdram_sha256"],
                  "rdram": str(output / "capture" / "state-extract" /
                               f"frame-{target:06d}.rdram")}
    except Exception as error:
        result = {**request, "complete": False, "error": str(error)}
        (output / "sample-result.json").write_text(json.dumps(result, indent=2) + "\n")
        raise
    (output / "sample-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--frame", type=int, required=True)
    parser.add_argument("--interval", type=int, default=5000)
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()
    print(json.dumps(sample(args.output, args.batch_root, args.frame,
                            interval=args.interval, timeout=args.timeout)))


if __name__ == "__main__":
    main()
