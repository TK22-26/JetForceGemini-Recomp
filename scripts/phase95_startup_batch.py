"""Run and verify independent fresh-gameplay startup repetitions."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def inspect_job(path):
    manifest = json.loads((path / "manifest.json").read_text())
    startup = json.loads((path / "startup-result.json").read_text())
    movement = json.loads((path / "movement-result.json").read_text())
    bridge = (path / "bridge-result.txt").read_text().strip()
    state = startup["state"]
    startup_hash = hashlib.sha256((path / "keyboard-entry.rdram").read_bytes()).hexdigest()
    final_hash = hashlib.sha256((path / "observation.rdram").read_bytes()).hexdigest()
    checks = {"fresh_save": manifest["initial_save"] == "fresh isolated worker",
              "gameplay_endpoint": startup["endpoint"] == "player-mode-16" and
                                   state["front_mode"] == 16 and
                                   state["level_number"] == 92 and bool(state["player"]),
              "checkpoint_continuation": movement.get("checkpoint_continuation_equal") is True and
                                         movement.get("checkpoint_steps") == 6,
              "clean_stop": bridge == "stopped"}
    pins = {key: manifest[key] for key in ("rom_sha256", "emulator_sha256", "config_sha256",
                                              "script_sha256", "runtime_sha256")}
    return {"session": manifest["session"], "pins": pins, "checks": checks,
            "frame": state["frame"], "polls": state["polls"],
            "player": state["player"], "startup_sha256": startup_hash,
            "final_sha256": final_hash, "passed": all(checks.values())}


def run_batch(root, emulator, rom, rom_sha256, count):
    if root.exists():
        raise ValueError("batch output must not already exist")
    if not 1 <= count <= 10:
        raise ValueError("startup repeat count must be 1..10")
    root.mkdir(parents=True)
    started = time.monotonic()
    records = []
    for index in range(count):
        job = root / f"job-{index:02d}"
        command = [sys.executable, "-m", "scripts.phase95_startup", str(job),
                   "--emulator", str(emulator), "--rom", str(rom),
                   "--rom-sha256", rom_sha256, "--verify-gameplay-checkpoint"]
        print(json.dumps({"starting": index, "job": str(job)}), flush=True)
        with (root / f"job-{index:02d}.stdout.log").open("w") as stdout, \
                (root / f"job-{index:02d}.stderr.log").open("w") as stderr:
            result = subprocess.run(command, stdout=stdout, stderr=stderr, check=False)
        record = {"index": index, "output": str(job), "exit_code": result.returncode}
        if result.returncode == 0:
            try:
                record.update(inspect_job(job))
                unique = record["session"] not in {item.get("session") for item in records}
                record["checks"]["unique_session"] = unique
                record["passed"] = record["passed"] and unique
            except (OSError, ValueError, KeyError, TypeError) as exc:
                record.update(passed=False, artifact_error=str(exc))
        else:
            record["passed"] = False
        records.append(record)
        summary = {"kind": "jfg-phase95-startup-repeat-batch", "acceptance": False,
                   "requested": count, "completed": len(records),
                   "passed": sum(item["passed"] for item in records),
                   "unique_startup_hashes": len({item["startup_sha256"] for item in records
                                                 if "startup_sha256" in item}),
                   "unique_final_hashes": len({item["final_sha256"] for item in records
                                               if "final_sha256" in item}),
                   "elapsed_seconds": time.monotonic() - started,
                   "jobs": records,
                   "limitations": "startup and checkpoint restore only; no Goldwood encounter or pickup"}
        (root / "batch-result.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps({"finished": index, "passed": record["passed"],
                          "exit_code": result.returncode}), flush=True)
        if not record["passed"]:
            raise RuntimeError(f"startup repeat {index} failed; retained {job}")
    return summary


def audit_batch(root):
    recorded = json.loads((root / "batch-result.json").read_text())
    if recorded.get("kind") != "jfg-phase95-startup-repeat-batch":
        raise ValueError("not a startup repeat batch")
    count = recorded["requested"]
    if not 1 <= count <= 10 or recorded["completed"] != count:
        raise ValueError("startup batch is incomplete")
    jobs = []
    for index in range(count):
        job = inspect_job(root / f"job-{index:02d}")
        job["index"] = index
        jobs.append(job)
    sessions = {item["session"] for item in jobs}
    pins = {json.dumps(item["pins"], sort_keys=True) for item in jobs}
    entry_hashes = {item["startup_sha256"] for item in jobs}
    final_hashes = {item["final_sha256"] for item in jobs}
    result = {"kind": "jfg-phase95-startup-repeat-audit", "acceptance": False,
              "requested": count, "passed": sum(item["passed"] for item in jobs),
              "unique_sessions": len(sessions), "unique_pin_sets": len(pins),
              "unique_startup_hashes": len(entry_hashes),
              "unique_final_hashes": len(final_hashes),
              "repeat_gate_evidence": count == 10 and all(item["passed"] for item in jobs)
                                      and len(sessions) == 10 and len(pins) == 1,
              "jobs": jobs,
              "limitations": "fresh gameplay startup and restore only; not the ten seeded Goldwood scenario jobs"}
    (root / "batch-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--emulator", type=Path)
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--rom-sha256")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--audit-existing", action="store_true")
    args = parser.parse_args()
    if args.audit_existing:
        report = audit_batch(args.output)
        print(json.dumps({key: value for key, value in report.items() if key != "jobs"}, indent=2))
    else:
        if args.emulator is None or args.rom is None or args.rom_sha256 is None:
            parser.error("new batches require emulator, ROM, and ROM digest")
        run_batch(args.output, args.emulator, args.rom, args.rom_sha256, args.count)


if __name__ == "__main__":
    main()
