"""Bounded, restartable post-capture supervisor for the private Japanese TAS.

Waits for the existing full capture to seal; then extracts all batch states,
runs bounded 5k sample-grid jobs, and refreshes the route atlas.
Never launches or changes the full capture or the visible viewer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import time

from scripts import phase95_tas_capture as capture
from scripts import phase95_tas_route_atlas as atlas_module
from scripts import phase95_tas_sample as sampler
from scripts import phase95_tas_sample_grid as grid
from scripts import phase95_tas_state_batch as state_batch
from scripts import phase95_tas_state_extract as state_extract


KIND = "jfg-phase95-jp-tas-followthrough"
PLAN_NAME = "followthrough-plan.json"
STATUS_NAME = "followthrough-status.json"
SPACING = 5000


def _batch_sealed(batch_root: Path) -> bool:
    path = batch_root / "batch-result.json"
    if not path.exists():
        return False
    try:
        value = state_batch.read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False  # An in-flight batch may be replacing its summary.
    if value.get("kind") != state_batch.PLAN_KIND or value.get("schema") != 1:
        raise ValueError("batch result kind or schema changed")
    return value.get("complete") is True


def _status(output: Path, plan: dict, *, state: str, jobs_started: int,
            state_index: dict | None = None, grid_progress: dict | None = None,
            atlas: dict | None = None, error: str | None = None,
            disk: dict | None = None) -> dict:
    complete = (state == "complete" and state_index is not None and
                state_index.get("complete") is True and
                grid_progress is not None and grid_progress.get("complete") is True and
                atlas is not None and atlas.get("route_complete") is True and
                atlas.get("grid_complete") is True and
                atlas.get("grid_provenance") is not None)
    report = {"kind": KIND, "schema": 1, "status": state,
              "complete": complete, "full_game_acceptance": False,
              "atlas_scope": ("sealed endpoints plus validated grid samples; "
                              "transition brackets only")
                  if atlas is not None and atlas.get("grid_provenance") is not None
                  else "sealed segment endpoints only",
              "source_batch": plan["source_batch"],
              "source_batch_plan_sha256": plan["source_batch_plan_sha256"],
              "jobs_started_this_invocation": jobs_started,
              "state_segments_extracted": (state_index or {}).get("segments_extracted"),
              "state_index_complete": (state_index or {}).get("complete", False),
              "grid_samples_complete": (grid_progress or {}).get("samples_complete"),
              "grid_targets_total": (grid_progress or {}).get("targets_total"),
              "grid_complete": (grid_progress or {}).get("complete", False),
              "atlas_route_complete": (atlas or {}).get("route_complete", False),
              "atlas_grid_complete": (atlas or {}).get("grid_complete", False),
              "disk_free_bytes": (disk or {}).get("free"),
              "disk_required_bytes": (disk or {}).get("required"),
              "state_index_sha256": capture.digest(Path(plan["source_batch"]) /
                                                  state_batch.INDEX_NAME)
                  if state_index is not None else None,
              "grid_ledger_sha256": capture.digest(output / "grid" / grid.LEDGER_NAME)
                  if grid_progress is not None else None,
              "atlas_sha256": capture.digest(Path(plan["source_batch"]) /
                                             atlas_module.OUTPUT_NAME)
                  if atlas is not None else None,
              "error": error}
    grid.write_json_atomic(output / STATUS_NAME, report)
    return report


def _disk_headroom(output: Path, emulator_dir: Path, reserve_mib: int) -> dict:
    source_bytes = sum(path.stat().st_size for path in emulator_dir.rglob("*")
                       if path.is_file())
    free = shutil.disk_usage(output).free
    # One worker copies the emulator and writes a state, screenshots and 8 MiB
    # RDRAM. Keep a further 256 MiB workload margin plus the user reserve.
    required = (reserve_mib * 1024 * 1024 + 2 * source_bytes +
                2 * state_extract.RDRAM_SIZE + 256 * 1024 * 1024)
    return {"free": free, "required": required,
            "source_emulator_bytes": source_bytes}


def run_followthrough(output: Path, batch_root: Path, *,
                      wait_seconds: int = 3600, poll_seconds: int = 30,
                      max_jobs: int = 16, job_timeout: int = 900,
                      reserve_mib: int = 1024) -> dict:
    output, batch_root = Path(output).resolve(), Path(batch_root).resolve()
    private = sampler.PRIVATE_ROOT.resolve()
    if (not output.is_relative_to(private) or
            not batch_root.is_relative_to(private) or
            output == batch_root or output.is_relative_to(batch_root)):
        raise ValueError("follow-through and batch must be separate under tools/private")
    if (type(wait_seconds) is not int or not 0 <= wait_seconds <= 86400 or
            type(poll_seconds) is not int or not 1 <= poll_seconds <= 60 or
            type(max_jobs) is not int or not 0 <= max_jobs <= 128 or
            type(job_timeout) is not int or not 1 <= job_timeout <= 3600 or
            type(reserve_mib) is not int or not 256 <= reserve_mib <= 65536):
        raise ValueError("invalid bounded follow-through settings")
    source_plan = state_batch.validate_plan(batch_root)
    source_emulator = Path(source_plan["source_emulator"]).resolve().parent
    if output == source_emulator or output.is_relative_to(source_emulator):
        raise ValueError("follow-through output cannot be inside source emulator")
    plan = {"kind": KIND, "schema": 1,
            "semantic_status": "raw-unverified-jp",
            "source_batch": str(batch_root),
            "source_batch_plan_sha256": capture.digest(batch_root / "batch.json"),
            "grid_spacing": SPACING,
            "grid_interval": SPACING,
            "grid_job_timeout": job_timeout,
            "capture_lua_sha256": source_plan["pins"]["script_sha256"],
            "state_batch_script_sha256": capture.digest(Path(state_batch.__file__).resolve()),
            "state_extract_script_sha256": capture.digest(Path(state_extract.__file__).resolve()),
            "sample_script_sha256": capture.digest(Path(sampler.__file__).resolve()),
            "sample_grid_script_sha256": capture.digest(Path(grid.__file__).resolve()),
            "atlas_script_sha256": capture.digest(Path(atlas_module.__file__).resolve()),
            "followthrough_script_sha256": capture.digest(Path(__file__).resolve())}
    if output.exists():
        if not output.is_dir():
            raise ValueError("follow-through output is not a directory")
        if not (output / PLAN_NAME).exists():
            if any(output.iterdir()):
                raise ValueError("existing follow-through output has no plan")
            grid.write_json_atomic(output / PLAN_NAME, plan)
        elif state_batch.read_json(output / PLAN_NAME) != plan:
            raise ValueError("existing follow-through output has different source or scripts")
    else:
        output.mkdir(parents=True)
        grid.write_json_atomic(output / PLAN_NAME, plan)

    deadline = time.monotonic() + wait_seconds
    jobs_started = 0
    state_index = None
    grid_progress = None
    atlas = None
    try:
        while not _batch_sealed(batch_root):
            report = _status(output, plan, state="waiting-for-batch",
                             jobs_started=jobs_started)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return report
            time.sleep(min(poll_seconds, remaining))
        state_index = state_batch.index_batch(batch_root)
        if state_index.get("complete") is not True or state_index.get("errors"):
            raise ValueError("sealed batch state extraction did not fully validate")
        while True:
            remaining = deadline - time.monotonic()
            disk = _disk_headroom(output, source_emulator, reserve_mib)
            # The grid plan pins its per-job timeout, so keep it stable across
            # every pass and restart. Start only when a whole job budget fits.
            can_start = (jobs_started < max_jobs and remaining >= job_timeout and
                         disk["free"] >= disk["required"])
            grid_progress = grid.run_grid(
                output / "grid", batch_root, spacing=SPACING,
                max_jobs=1 if can_start else 0,
                interval=SPACING,
                timeout=job_timeout)
            jobs_started += grid_progress["jobs_started_this_invocation"]
            atlas = atlas_module.build_atlas(
                batch_root / state_batch.INDEX_NAME,
                grid_progress_path=output / "grid" / grid.LEDGER_NAME)
            grid_hash = capture.digest(output / "grid" / grid.LEDGER_NAME)
            if (not isinstance(atlas.get("grid_provenance"), dict) or
                    atlas["grid_provenance"].get("grid_progress_sha256") != grid_hash or
                    atlas.get("grid_complete") is not grid_progress.get("complete")):
                raise ValueError("route atlas did not seal current grid progress")
            if grid_progress.get("complete") is True:
                return _status(output, plan, state="complete",
                               jobs_started=jobs_started, state_index=state_index,
                               grid_progress=grid_progress, atlas=atlas, disk=disk)
            blocked_on_disk = (jobs_started < max_jobs and
                               remaining >= job_timeout and not can_start)
            report = _status(output, plan,
                             state="insufficient-disk" if blocked_on_disk else "sampling",
                             jobs_started=jobs_started, state_index=state_index,
                             grid_progress=grid_progress, atlas=atlas, disk=disk)
            if not can_start:
                return report
            if grid_progress["jobs_started_this_invocation"] != 1:
                raise ValueError("incomplete grid made no progress")
    except Exception as error:
        _status(output, plan, state="error", jobs_started=jobs_started,
                state_index=state_index, grid_progress=grid_progress,
                atlas=atlas, error=str(error))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--wait-seconds", type=int, default=3600)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--max-jobs", type=int, default=16)
    parser.add_argument("--job-timeout", type=int, default=900)
    parser.add_argument("--reserve-mib", type=int, default=1024)
    args = parser.parse_args()
    print(json.dumps(run_followthrough(
        args.output, args.batch_root, wait_seconds=args.wait_seconds,
        poll_seconds=args.poll_seconds, max_jobs=args.max_jobs,
        job_timeout=args.job_timeout, reserve_mib=args.reserve_mib)))


if __name__ == "__main__":
    main()
