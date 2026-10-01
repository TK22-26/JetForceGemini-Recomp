"""Restartable private grid of full-RDRAM Japanese TAS frame samples.

The full capture batch must be sealed first. Each invocation launches at most
``--max-jobs`` new isolated samples; prior outputs are revalidated, never
overwritten or deleted. The viewer and source batch are read-only inputs.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path

from scripts import phase95_tas_batch as batch
from scripts import phase95_tas_capture as capture
from scripts import phase95_tas_sample as sampler
from scripts import phase95_tas_state_batch as state_batch
from scripts import phase95_tas_state_extract as state_extract


KIND = "jfg-phase95-jp-tas-sample-grid"
PLAN_NAME = "sample-grid.json"
LEDGER_NAME = "sample-grid-progress.json"


@contextmanager
def grid_lock(output: Path):
    """OS-held advisory lock; a crashed process releases it automatically."""
    path = output / "sample-grid.lock"
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("another sample-grid invocation owns this root") from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def write_json_atomic(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


def grid_targets(frames: int, segment_frames: int, spacing: int) -> list[int]:
    if not 1 <= spacing <= frames:
        raise ValueError("grid spacing is outside movie length")
    sealed_ends = {last for _, last in batch._segments(frames, segment_frames)}
    return [frame for frame in range(spacing - 1, frames, spacing)
            if frame not in sealed_ends]


def sealed_batch(root: Path, plan: dict) -> list[tuple[int, Path]]:
    """Verify the full sequential state chain, not only batch-result.json."""
    summary = state_batch.read_json(root / "batch-result.json")
    ranges = list(batch._segments(plan["pins"]["movie_frames"],
                                  plan["segment_frames"]))
    if (summary.get("kind") != batch.KIND or summary.get("schema") != 1 or
            summary.get("complete") is not True or
            summary.get("segments_total") != len(ranges) or
            summary.get("segments_complete") != len(ranges) or
            summary.get("last_complete_frame") != plan["pins"]["movie_frames"] - 1):
        raise ValueError("full TAS capture batch is not sealed")
    previous = None
    selected = []
    for first, last in ranges:
        segment = root / "segments" / f"segment-{first:06d}-{last:06d}"
        attempt = batch._complete_attempt(segment, first, last,
                                          plan["pins"], previous)
        if attempt is None:
            raise ValueError(f"sealed batch has a missing segment: {segment}")
        selected.append((last, attempt))
        previous = attempt
    return selected


def predecessor(selected: list[tuple[int, Path]], target: int) -> Path | None:
    prior = None
    for last, attempt in selected:
        if last >= target:
            break
        prior = attempt
    return prior


def validate_sample(attempt: Path, root: Path, plan: dict,
                    target: int, prior: Path | None, *,
                    interval: int, timeout: int) -> dict:
    result_path = attempt / "sample-result.json"
    result = state_batch.read_json(result_path)
    request = state_batch.read_json(attempt / "sample-request.json")
    source_plan_hash = capture.digest(root / "batch.json")
    parent_hash = (state_batch.read_json(prior / "result.json")
                   ["continuation_sha256"] if prior is not None else None)
    first = (state_batch.read_json(prior / "result.json")["last"] + 1
             if prior is not None else 0)
    expected = {"kind": sampler.KIND, "schema": 1, "complete": True,
                "semantic_status": "raw-unverified-jp", "target_frame": target,
                "capture_first": first, "source_batch": str(root),
                "source_batch_plan_sha256": source_plan_hash,
                "sealed_predecessor": str(prior) if prior is not None else None,
                "sealed_predecessor_sha256": parent_hash,
                "sampler_sha256": capture.digest(Path(sampler.__file__).resolve()),
                "capture_driver_sha256": plan["driver_sha256"],
                "capture_lua_sha256": plan["pins"]["script_sha256"],
                "interval": interval, "timeout": timeout}
    if any(result.get(key) != value for key, value in expected.items()):
        raise ValueError(f"sample result pins, target or lineage differ: {attempt}")
    if any(request.get(key) != value for key, value in expected.items()
           if key != "complete") or \
            request.get("interval") != result.get("interval") or \
            request.get("timeout") != result.get("timeout"):
        raise ValueError(f"sample request/result mismatch: {attempt}")
    capture_dir = attempt / "capture"
    captured = state_batch.read_json(capture_dir / "result.json")
    if (captured.get("complete") is not True or
            captured.get("first") != first or captured.get("last") != target or
            captured.get("resume_from") != expected["sealed_predecessor"] or
            captured.get("parent_continuation_sha256") != parent_hash or
            any(captured.get(key) != value for key, value in plan["pins"].items()) or
            result.get("capture_result_sha256") != capture.digest(capture_dir / "result.json") or
            result.get("continuation_sha256") != captured.get("continuation_sha256")):
        raise ValueError(f"sample capture pins or digest differ: {attempt}")
    capture.validate_resume(capture_dir, plan["pins"], target + 1)
    capture.parse_trace(capture_dir / "frames.tsv", first, target)
    extracted = state_batch.validate_extract(capture_dir, target, captured)
    rdram = capture_dir / "state-extract" / f"frame-{target:06d}.rdram"
    if result.get("rdram") != str(rdram) or \
            result.get("rdram_sha256") != extracted["rdram_sha256"]:
        raise ValueError(f"sample RDRAM identity differs: {attempt}")
    return {"frame": target, "attempt": str(attempt),
            "rdram": str(rdram), "rdram_sha256": extracted["rdram_sha256"],
            "continuation_sha256": captured["continuation_sha256"],
            "sample_result_sha256": capture.digest(result_path)}


def _find_complete(sample_dir: Path, root: Path, plan: dict, target: int,
                   prior: Path | None, *, interval: int,
                   timeout: int) -> tuple[dict | None, int]:
    complete = []
    failed = 0
    for attempt in sorted(sample_dir.glob("attempt-*")) if sample_dir.exists() else ():
        if not attempt.is_dir() or not attempt.name[8:].isdigit():
            raise ValueError(f"unexpected sample attempt: {attempt}")
        result_path = attempt / "sample-result.json"
        if not result_path.exists():
            failed += 1  # Interrupted attempt is preserved, not reused.
            continue
        result = state_batch.read_json(result_path)
        if result.get("complete") is not True:
            failed += 1
            continue
        complete.append(validate_sample(attempt, root, plan, target, prior,
                                        interval=interval, timeout=timeout))
    if len(complete) > 1:
        raise ValueError(f"multiple complete samples for frame {target}")
    return (complete[0] if complete else None), failed


def run_grid(output: Path, batch_root: Path, *, spacing: int = 5000,
             max_jobs: int = 1, timeout: int = 3600,
             interval: int = 5000) -> dict:
    output, batch_root = Path(output).resolve(), Path(batch_root).resolve()
    private = sampler.PRIVATE_ROOT.resolve()
    if not output.is_relative_to(private) or not batch_root.is_relative_to(private) or \
            output == batch_root or output.is_relative_to(batch_root):
        raise ValueError("grid and batch must be separate under tools/private")
    if type(max_jobs) is not int or not 0 <= max_jobs <= 32 or \
            type(timeout) is not int or timeout < 1 or \
            type(interval) is not int or not 1 <= interval <= capture.MAX_SEGMENT_FRAMES:
        raise ValueError("invalid bounded grid job settings")
    batch_plan = state_batch.validate_plan(batch_root)
    selected = sealed_batch(batch_root, batch_plan)
    if output == Path(batch_plan["source_emulator"]).resolve().parent or \
            output.is_relative_to(Path(batch_plan["source_emulator"]).resolve().parent):
        raise ValueError("grid output cannot be inside source emulator")
    targets = grid_targets(batch_plan["pins"]["movie_frames"],
                           batch_plan["segment_frames"], spacing)
    plan = {"kind": KIND, "schema": 1, "semantic_status": "raw-unverified-jp",
            "source_batch": str(batch_root),
            "source_batch_plan_sha256": capture.digest(batch_root / "batch.json"),
            "sampler_sha256": capture.digest(Path(sampler.__file__).resolve()),
            "grid_script_sha256": capture.digest(Path(__file__).resolve()),
            "extractor_sha256": capture.digest(Path(state_extract.__file__).resolve()),
            "spacing": spacing, "interval": interval, "timeout": timeout,
            "targets": targets, "movie_frames": batch_plan["pins"]["movie_frames"]}
    if output.exists():
        if not output.is_dir() or not (output / PLAN_NAME).is_file() or \
                state_batch.read_json(output / PLAN_NAME) != plan:
            raise ValueError("existing grid output has a different pinned plan")
    else:
        output.mkdir(parents=True)
        write_json_atomic(output / PLAN_NAME, plan)
    with grid_lock(output):
        entries = []
        failed_seen = 0
        jobs_started = 0
        errors = []
        for target in targets:
            prior = predecessor(selected, target)
            sample_dir = output / "samples" / f"frame-{target:06d}"
            try:
                found, failed = _find_complete(sample_dir, batch_root, batch_plan,
                                               target, prior, interval=interval,
                                               timeout=timeout)
                failed_seen += failed
                if found is not None:
                    entries.append(found)
                    continue
                if jobs_started >= max_jobs:
                    continue
                attempt = batch._next_attempt(sample_dir)
                jobs_started += 1
                sampler.sample(attempt, batch_root, target,
                               interval=interval, timeout=timeout)
                entries.append(validate_sample(attempt, batch_root, batch_plan,
                                               target, prior, interval=interval,
                                               timeout=timeout))
            except Exception as error:
                errors.append({"frame": target, "error": str(error)})
                break
        progress = {"kind": KIND, "schema": 1,
                    "semantic_status": "raw-unverified-jp",
                    "grid_plan_sha256": capture.digest(output / PLAN_NAME),
                    "targets_total": len(targets), "samples_complete": len(entries),
                    "jobs_started_this_invocation": jobs_started,
                    "failed_attempts_seen": failed_seen,
                    "last_sampled_frame": entries[-1]["frame"] if entries else None,
                    "complete": len(entries) == len(targets) and not errors,
                    "errors": errors, "entries": entries}
        write_json_atomic(output / LEDGER_NAME, progress)
        if errors:
            raise RuntimeError(f"sample grid stopped at frame {errors[0]['frame']}: "
                               f"{errors[0]['error']}")
        return progress


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--spacing", type=int, default=5000)
    parser.add_argument("--max-jobs", type=int, default=1)
    parser.add_argument("--interval", type=int, default=5000)
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()
    print(json.dumps(run_grid(args.output, args.batch_root,
                              spacing=args.spacing, max_jobs=args.max_jobs,
                              interval=args.interval, timeout=args.timeout)))


if __name__ == "__main__":
    main()
