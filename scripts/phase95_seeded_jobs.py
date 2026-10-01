"""Run bounded, restartable Phase 9.5 Goldwood objective-selection jobs.

The seed currently selects one of three reviewed objectives. It does not yet
perturb low-level navigation, so this is a reliability/branch batch rather
than proof of varied paths or complete milestone-B acceptance.
"""
import argparse
import json
from pathlib import Path
import time

from scripts.phase95_bridge import Worker, digest
from scripts.phase95_death_retry_scenario import run as run_death_retry
from scripts.phase95_goldwood_east_scenario import run as run_east
from scripts.phase95_goldwood_scenario import run as run_south


GOALS = ("south21", "east48", "death_retry")
RESULT_FILES = {"south21": "scenario-result.json",
                "east48": "scenario-result.json",
                "death_retry": "death-retry-result.json"}


def plan(seed_start=0, count=10):
    if type(seed_start) is not int or seed_start < 0 or \
            type(count) is not int or not 1 <= count <= 100:
        raise ValueError("invalid seeded-job range")
    return [{"seed": seed, "objective": GOALS[seed % len(GOALS)]}
            for seed in range(seed_start, seed_start + count)]


def run_batch(output, emulator, rom, rom_sha256, south_checkpoint,
              east_checkpoint, death_checkpoint, south_proposal, east_proposal,
              upper_proposal, east_finish_template, *, seed_start=0,
              count=10, max_jobs=None, max_attempts=2, resume=False):
    output = Path(output).resolve()
    if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise ValueError("invalid per-seed attempt budget")
    if max_jobs is not None and (type(max_jobs) is not int or
                                 not 1 <= max_jobs <= count):
        raise ValueError("invalid invocation job budget")
    paths = {key: Path(value).resolve() for key, value in {
        "emulator": emulator, "rom": rom,
        "south_checkpoint": south_checkpoint,
        "east_checkpoint": east_checkpoint,
        "death_checkpoint": death_checkpoint,
        "south_proposal": south_proposal, "east_proposal": east_proposal,
        "upper_proposal": upper_proposal,
        "east_finish_template": east_finish_template}.items()}
    if digest(paths["rom"]) != rom_sha256:
        raise ValueError("ROM identity mismatch")
    jobs = plan(seed_start, count)
    objective = {"kind": "jfg-phase95-seeded-goldwood-batch", "schema": 1,
                 "acceptance": False, "seed_start": seed_start,
                 "job_count": count, "max_attempts": max_attempts,
                 "selection_policy": "seed modulo three selects south21/east48/death_retry; low-level paths are unseeded",
                 "jobs": jobs, "rom_sha256": rom_sha256,
                 "assets": {key: {"path": str(path), "sha256": digest(path)}
                            for key, path in paths.items()},
                 "limitations": "all three objectives use distinct reviewed frontiers; native parity, path variation, and a common destination checkpoint remain open"}
    if resume:
        if json.loads((output / "batch-objective.json").read_text()) != objective:
            raise ValueError("batch objective or pinned assets changed")
    else:
        output.mkdir(parents=True, exist_ok=False)
        (output / "batch-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    started = time.monotonic()
    completed = []
    launched = 0
    journal = output / "batch-completed.jsonl"
    logged = {json.loads(line)["seed"] for line in journal.read_text().splitlines()} \
        if journal.exists() else set()
    for job in jobs:
        root = output / f"seed-{job['seed']:04d}"
        goal = job["objective"]
        successful = None
        for attempt in range(1, max_attempts + 1):
            candidate = root / f"attempt-{attempt:02d}"
            result_path = candidate / RESULT_FILES[goal]
            if result_path.exists():
                result = json.loads(result_path.read_text())
                if result.get("completed"):
                    successful = {"seed": job["seed"], "objective": goal,
                                  "attempt": attempt, "result": result,
                                  "artifact_root": str(candidate)}
                    break
            if candidate.exists():
                # Preserve partial/failed attempts and try the next bounded slot.
                continue
            if max_jobs is not None and launched >= max_jobs:
                break
            root.mkdir(parents=True, exist_ok=True)
            launched += 1
            try:
                with Worker(candidate, paths["emulator"], paths["rom"],
                            Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                            rom_sha256) as worker:
                    worker.observe()
                    checkpoint = paths[{"south21": "south_checkpoint",
                                        "east48": "east_checkpoint",
                                        "death_retry": "death_checkpoint"}[goal]]
                    worker.import_checkpoint(checkpoint)
                    if goal == "south21":
                        result = run_south(worker, paths["south_proposal"])
                    elif goal == "east48":
                        result = run_east(worker, paths["east_proposal"],
                                          paths["upper_proposal"],
                                          paths["east_finish_template"])
                    else:
                        result = run_death_retry(worker)
            except Exception as error:
                (candidate / "batch-attempt-failure.json").write_text(
                    json.dumps({"seed": job["seed"], "objective": goal,
                                "attempt": attempt,
                                "classification": type(error).__name__,
                                "detail": str(error)}, indent=2) + "\n")
                result = None
            if result is not None and result.get("completed"):
                successful = {"seed": job["seed"], "objective": goal,
                              "attempt": attempt, "result": result,
                              "artifact_root": str(candidate)}
                break
        if successful is None:
            # Incomplete jobs are never counted as passes. A later --resume
            # invocation can use unused attempt slots without deleting evidence.
            break
        completed.append(successful)
        if job["seed"] not in logged:
            with journal.open("a") as stream:
                stream.write(json.dumps({"seed": successful["seed"],
                                         "objective": goal,
                                         "attempt": successful["attempt"],
                                         "artifact_root": successful["artifact_root"]}) + "\n")
            logged.add(job["seed"])
        print(json.dumps({"seed": job["seed"], "objective": goal,
                          "attempt": successful["attempt"], "completed": True}),
              flush=True)
    summary = {**objective, "completed": len(completed) == count,
               "jobs_completed": len(completed),
               "jobs_launched_this_invocation": launched,
               "elapsed_seconds_this_invocation": time.monotonic() - started,
               "covered_objectives": sorted(set(item["objective"] for item in completed)),
               "native_parity_verified": False}
    (output / "batch-result.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    for name in ("emulator", "rom", "south-checkpoint", "east-checkpoint",
                 "death-checkpoint",
                 "south-proposal", "east-proposal", "upper-proposal",
                 "east-finish-template"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--max-jobs", type=int)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_batch(args.output, args.emulator, args.rom,
                               args.rom_sha256, args.south_checkpoint,
                               args.east_checkpoint, args.death_checkpoint,
                               args.south_proposal,
                               args.east_proposal, args.upper_proposal,
                               args.east_finish_template,
                               seed_start=args.seed_start, count=args.count,
                               max_jobs=args.max_jobs,
                               max_attempts=args.max_attempts,
                               resume=args.resume)))


if __name__ == "__main__":
    main()
